import asyncio
import base64
import functools
import inspect
import re
import ssl
from inspect import isawaitable
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, Union
from urllib.parse import urlparse

from pyppeteer.util import get_free_port
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.httputil import HTTPServerRequest
from tornado.log import app_log
from tornado.routing import _RuleList

BASE_HTML = '''
<html>
<head><title>main</title></head>
<body>
<h1 id="hello">Hello</h1>
<a id="link1" href="./1">link1</a>
<a id="link2" href="./2">link2</a>
</body>
</html>
'''


class BaseHandler(web.RequestHandler):
    def get(self) -> None:
        self.set_header(
            'Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0',
        )


def auth_api(username: str, password: str) -> bool:
    if username == 'user' and password == 'pass':
        return True
    else:
        return False


def basic_auth(auth: Callable[[str, str], bool]) -> Callable:
    def wrapper(f: Callable) -> Callable:
        def _request_auth(handler: Any) -> None:
            handler.set_header('WWW-Authenticate', 'Basic realm=JSL')
            handler.set_status(401)
            handler.finish()

        @functools.wraps(f)
        def new_f(*args: Any) -> None:
            handler = args[0]

            auth_header = handler.request.headers.get('Authorization')
            if auth_header is None:
                return _request_auth(handler)
            if not auth_header.startswith('Basic '):
                return _request_auth(handler)

            auth_decoded = base64.b64decode(auth_header[6:])
            username, password = auth_decoded.decode('utf-8').split(':', 2)

            if auth(username, password):
                f(*args)
            else:
                _request_auth(handler)

        return new_f

    return wrapper


class AuthHandler:
    @basic_auth(auth_api)
    def get(self) -> None:
        super().get()
        self.write('ok')


class _StaticFileHandler(web.StaticFileHandler):
    # todo: feels like a hack...
    callbacks = {}

    @classmethod
    def add_one_time_request_precondition(
        cls, path: str, precondition: Union[Awaitable, Callable[[], None]], should_return: bool = False
    ):
        async def caller(request_handler):
            func_res = precondition
            if callable(precondition):
                # only pass in request handler if we detect one, and only one arg
                if len(inspect.getfullargspec(precondition).args) == 1:
                    func_res = precondition(request_handler)
                else:
                    func_res = precondition()
            if isawaitable(func_res):
                return await func_res

        stripped = urlparse(path).path
        if stripped not in cls.callbacks:
            cls.callbacks[stripped] = []
        cls.callbacks[stripped].append((caller, should_return))

    async def prepare(self) -> Optional[Awaitable[None]]:
        path = self.request.path
        if path in self.callbacks:
            # sort callbacks first by should_return, then by their index
            callbacks = sorted(self.callbacks[path], key=lambda x: (x[1], self.callbacks[path].index(x)))
            if len([True for callback_fn, should_return in callbacks if should_return]) > 1:
                app_log.warning(
                    'More than one callback with should_return=True specified! '
                    'This means that every callback after the first one will be completely ignored!'
                )
            del self.callbacks[path]
            for callback, should_return in callbacks:
                await callback(self)
                if should_return:
                    return

    async def post(self, path: str):
        return await self.get(path)


class _Application(web.Application):
    def __init__(
        self,
        handlers: _RuleList = None,
        default_host: str = None,
        transforms: List[Type["OutputTransform"]] = None,
        **settings: Any,
    ) -> None:
        self._static_handler_instance = handlers[0][1]
        super().__init__(handlers, default_host, transforms, **settings)

    def add_one_time_request_delay(self, path: str, delay: float):
        self.add_one_time_request_precondition(path, precondition=asyncio.sleep(delay))

    def one_time_redirect(self, from_path: str, to: str):
        to = urlparse(to).path

        def redirector(handler):
            handler.redirect(to)

        self.add_one_time_request_precondition(from_path, redirector, should_return=True)

    def add_one_time_request_resp(
        self, path: str, resp: Union[str, bytes] = None, method: str = 'GET', status: int = 200
    ):
        method = method.lower()

        class OneTimeHandler(web.RequestHandler):
            has_completed_req = False

            def one_time_responder(self, *__, **_):
                self.set_status(status)
                if resp is not None:
                    self.write(resp)
                self.has_completed_req = True

        setattr(OneTimeHandler, method, OneTimeHandler.one_time_responder)
        self.add_handlers(r'.*', [(re.escape(urlparse(path).path), OneTimeHandler)])

    def add_one_time_request_precondition(
        self, path: str, precondition: Union[Awaitable, Callable[[], None]], should_return: bool = False
    ):
        self._static_handler_instance.add_one_time_request_precondition(path, precondition, should_return)

    def add_one_time_header_for_request(self, path: str, headers: Dict[str, str]):
        self._static_handler_instance.add_one_time_request_precondition(
            path, lambda handler: [handler.set_header(k, v) for k, v in headers.items()]
        )

    def waitForRequest(self, path: str) -> Awaitable[HTTPServerRequest]:
        fut = asyncio.get_event_loop().create_future()

        def future_resolver(handler):
            fut.set_result(handler.request)

        self._static_handler_instance.add_one_time_request_precondition(path, future_resolver)
        return fut


def get_application() -> _Application:
    static_path = Path(__file__).parents[1] / 'assets'
    handlers = [
        # required that the _StaticFileHandler is the first handler
        (r'/(.*)', _StaticFileHandler, {'path': static_path.name}),
    ]
    return _Application(handlers, static_path=static_path)


if __name__ == '__main__':
    app = get_application()
    port = get_free_port()
    app.listen(port)
    print(f'server running on http://localhost:{port}')
    asyncio.get_event_loop().run_forever()
