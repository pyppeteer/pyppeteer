import asyncio
import inspect
import logging
import ssl
from inspect import isawaitable
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.log import web_logger
from aiohttp.web_app import _Middleware
from aiohttp.web_urldispatcher import UrlDispatcher


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
        self.pre_request_callbacks = {}
        super().__init__(
            logger=logger,
            router=router,
            middlewares=middlewares,
            handler_args=handler_args,
            client_max_size=client_max_size,
            loop=loop,
            debug=debug,
        )
        self.router._frozen = False

    @staticmethod
    def get_pre_request_caller(precondition):
        async def caller(request):
            func_res = precondition
            if callable(precondition):
                args = []
                if len(inspect.getfullargspec(precondition).args) == 1:
                    # only pass in request handler if we detect one, and only one arg
                    args = [request]
                func_res = precondition(*args)
            if isawaitable(func_res):
                return await func_res

        return caller

    def add_pre_request_callback(self, path: str, precondition, should_return: bool):
        path = urlparse(path).path.strip('/')
        caller = self.get_pre_request_caller(precondition)

        if path not in self.pre_request_callbacks:
            self.pre_request_callbacks[path] = []
        self.pre_request_callbacks[path].append((caller, should_return))

    def set_one_time_redirect(self, from_path: str, to_path: str):
        def raiser():
            raise web.HTTPFound(to_path)

        self.add_pre_request_callback(from_path, raiser, should_return=True)


async def app_runner(assets_path, free_port: int = None):
    free_port = free_port

    async def static_file_serve(request):
        path = request.match_info['path']
        if path in request.app.pre_request_callbacks:
            callbacks = sorted(
                request.app.pre_request_callbacks.pop(path),
                key=lambda item: (item[1], request.app.pre_request_callbacks[path].index(item)),
            )
            for callback, should_return in callbacks:
                res = await callback(request)
                if should_return:
                    return res

        return web.FileResponse(assets_path / request.match_info['path'])

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
    app = loop.run_until_complete(app_runner(Path(__file__).parents[1] / 'assets_path', 55015))
    while True:
        loop.run_until_complete(asyncio.sleep(0.5))
