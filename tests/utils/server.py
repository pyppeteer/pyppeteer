import asyncio
import inspect
import logging
import ssl
from functools import partial
from inspect import isawaitable
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, Optional, Union
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.log import web_logger
from aiohttp.web_app import _Middleware
from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_urldispatcher import UrlDispatcher

RequestPrecondition = Union[Callable, Callable[[web.Request], Any], Awaitable[Any]]


class WrappedApplication(web.Application):
    def __init__(
        self,
        *,
        logger: logging.Logger = web_logger,
        router: Optional[UrlDispatcher] = None,
        middlewares: Iterable[_Middleware] = (),
        handler_args: Mapping[str, Any] = None,
        client_max_size: int = 1024 ** 2,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        debug: Any = ...,
    ) -> None:
        self.pre_request_subscribers = {}
        self.raisable_statuses = {
            204: lambda: web.HTTPNoContent(),
        }
        super().__init__(
            logger=logger,
            router=router,
            middlewares=middlewares,
            handler_args=handler_args,
            client_max_size=client_max_size,
            loop=loop,
            debug=debug,
        )
        # required so that we can dynamically add and remove routes
        self.router._frozen = False
        self.headers = {}

    @staticmethod
    def get_pre_request_caller(precondition: RequestPrecondition):
        """
        Returns an async function which executes (if necessary) precondition with the single argument of request
         (if necessary) and awaits the result (if necessary). This allows precondition to be an awaitable (eg future),
         async, or nonasync functions
        Args:
            precondition: (async or nonasync) function or awaitable

        Returns:
            function which waits for the completion of precondition
        """

        async def caller(request):
            func_res = precondition
            if callable(precondition):
                args = []
                # only pass in request handler if we detect one, and only one arg
                if len(inspect.getfullargspec(precondition).args) == 1:
                    args = [request]
                func_res = precondition(*args)
            if isawaitable(func_res):
                func_res = await func_res
            return func_res

        return caller

    def add_pre_request_subscriber(self, path: str, precondition: RequestPrecondition, should_return: bool):
        path = urlparse(path).path.strip('/')

        caller = self.get_pre_request_caller(precondition)

        if path not in self.pre_request_subscribers:
            self.pre_request_subscribers[path] = []
        self.pre_request_subscribers[path].append((caller, should_return))

    def set_one_time_redirects(self, from_path: str, *path_items: str):
        last_path = from_path
        for to_path in path_items:

            def redirect_raiser(redirect_path):
                raise web.HTTPFound(redirect_path)

            # we need to wrap the fn in partial to 'capture' to_path at the current iteration in the loop
            # otherwise, every endpoint will (incorrectly) redirect to the last item in the chain
            self.add_pre_request_subscriber(last_path, partial(redirect_raiser, to_path), should_return=True)
            last_path = to_path

    def set_one_time_response(
        self, path: str, response: str = None, status: int = 200, headers: Dict = None,
            content_type: str = 'text/html', **kwargs
    ):
        """
        kwargs - any param web_response::Response class allows.
        """
        def responder():

            if status in self.raisable_statuses:
                raise self.raisable_statuses[status]()
            return web.Response(body=response, status=status, headers=headers or {},
                                content_type=content_type, **kwargs)

        self.add_pre_request_subscriber(path, responder, should_return=True)

    def one_time_request_delay(self, path: str):
        fut = asyncio.get_event_loop().create_future()

        async def holder():
            await fut

        self.add_pre_request_subscriber(path, holder, should_return=False)
        return fut

    def waitForRequest(self, path: str):
        fut = asyncio.get_event_loop().create_future()

        def resolve_fut(req):
            fut.set_result(req)

        self.add_pre_request_subscriber(path, resolve_fut, should_return=False)
        return fut


def create_request_content_cache_fn(content):
    """
    Creates an async function which returns content. This is used in the context of a route handler to allow checking
    the request content after a response is sent (which isn't natively possible with aiohttp)
    Args:
        content: bytes to return

    Returns:
        async function returning content
    """

    async def cached_content():
        return content

    return cached_content


async def app_runner(assets_path, free_port):
    async def static_file_serve(request):
        path = request.match_info['path']
        try:
            headers = request.app.headers.pop(path)
        except KeyError:
            headers = {}

        # cache the request's content for later use
        request.read = create_request_content_cache_fn(await request.read())

        if path in request.app.pre_request_subscribers:
            # we make sure to remove the path ASAP, otherwise a unrelated request may be unintentionally mistreated
            callback_fns, should_returns = zip(*request.app.pre_request_subscribers.pop(path))
            # run all subscribers at once
            gathered = await asyncio.gather(*[sub(request) for sub in callback_fns], return_exceptions=True)
            for result, should_return in zip(gathered, should_returns):
                # aiohttp use exceptions for HTTP responses (sometimes) eg 404, 302
                if should_return:
                    if isinstance(result, Exception):
                        raise result
                    return result

        file_path = assets_path / request.match_info['path']
        if not file_path.exists():
            raise HTTPNotFound()  # ie 404
        return web.FileResponse(file_path, headers=headers)

    app = WrappedApplication()
    app.add_routes([web.get('/{path:.*}', static_file_serve), web.post('/{path:.*}', static_file_serve)])
    runner = web.AppRunner(app)
    await runner.setup()
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    cert_dir = Path(__file__).parent
    ssl_ctx.load_cert_chain(certfile=cert_dir / 'cert.pem', keyfile=cert_dir / 'private.key')
    http_site = web.TCPSite(runner, port=free_port)
    https_site = web.TCPSite(runner, port=free_port + 1, ssl_context=ssl_ctx)
    await asyncio.gather(http_site.start(), https_site.start())
    return app


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app_runner(Path(__file__).parents[1] / 'assets_path', 55015))
    while True:
        loop.run_until_complete(asyncio.sleep(0.5))
