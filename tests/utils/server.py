import asyncio
import base64
import functools
from inspect import isawaitable
from pathlib import Path
from typing import Callable, Any, Dict, Union, Awaitable, List, Type
from urllib.parse import urlparse

from tornado import web
from tornado.httputil import HTTPServerRequest
from tornado.log import access_log
from tornado.routing import _RuleList

from pyppeteer.util import get_free_port

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
    request_headers = {}
    one_time_request_headers = {}
    callbacks = {}
    request_preconditions = {}
    request_resp = {}

    @classmethod
    def set_request_header(cls, path: str, headers: Dict[str, str], one_time: bool = False):
        (cls.one_time_request_headers if one_time else cls.request_headers)[path.strip('/')] = headers

    @classmethod
    def add_one_time_callback(cls, path: str, func: Callable[[HTTPServerRequest], Any]):
        stripped = path.strip('/')
        if stripped not in cls.callbacks:
            cls.callbacks[stripped] = []
        cls.callbacks[stripped].append(func)

    @classmethod
    def add_one_time_request_precondition(cls, path: str, precondition: Union[Awaitable, Callable[[], None]]):
        cls.add_one_time_callback(path, lambda _: precondition() if callable(precondition) else precondition)

    @classmethod
    def add_one_time_request_resp(cls, path: str, resp: bytes):
        cls.request_resp[path.strip('/')] = resp

    async def get(self, path: str, include_body: bool = True) -> None:
        if path in self.callbacks:
            callbacks = self.callbacks[path][:]
            del self.callbacks[path]
            for callback in callbacks:
                func_res = callback(self.request)
                if isawaitable(func_res):
                    await func_res

        headers = self.request_headers.get(path, {})
        if path in self.one_time_request_headers:
            headers = self.one_time_request_headers[path]
            del self.one_time_request_headers[path]

        if headers:
            [self.set_header(k, v) for k, v in headers.items()]

        if path in self.request_resp:
            resp = self.request_resp[path]
            del self.request_resp[path]
            self.write(resp)
        else:
            await super().get(path, include_body)


class _Application(web.Application):
    def __init__(
        self,
        handlers: _RuleList = None,
        default_host: str = None,
        transforms: List[Type["OutputTransform"]] = None,
        **settings: Any,
    ) -> None:
        self._handlers = handlers
        self._static_handler_instance = self._handlers[0][1]
        super().__init__(handlers, default_host, transforms, **settings)

    def add_one_time_request_delay(self, path: str, delay: float):
        async def _delay():
            await asyncio.sleep(delay)

        self.add_one_time_request_precondition(path, precondition=_delay)

    def add_one_time_request_resp(self, path: str, resp: bytes):
        self._static_handler_instance.add_one_time_request_resp(urlparse(path), resp)

    def add_one_time_request_precondition(self, path: str, precondition: Union[Awaitable, Callable[[], None]]):
        self._static_handler_instance.add_one_time_request_precondition(urlparse(path).path, precondition)

    def add_one_time_header_for_request(self, path: str, headers: Dict[str, str]):
        self._static_handler_instance.set_request_header(urlparse(path).path, headers, True)

    def add_header_for_request(self, path: str, headers: Dict[str, str]):
        self._static_handler_instance.set_request_header(urlparse(path).path, headers, False)

    def waitForRequest(self, path: str) -> Awaitable[HTTPServerRequest]:
        fut = asyncio.get_event_loop().create_future()

        def resolve_fut(req):
            fut.set_result(req)

        self._static_handler_instance.add_one_time_callback(urlparse(path).path, resolve_fut)
        return fut


def get_application() -> _Application:
    static_path = Path(__file__).parents[1] / 'assets'
    handlers = [
        # required that the _StaticFileHandler is the first handler
        (r'/(.*)', _StaticFileHandler, {'path': static_path.name}),
    ]
    return _Application(handlers, static_path=static_path,)


if __name__ == '__main__':
    app = get_application()
    port = get_free_port()
    app.listen(port)
    print(f'server running on http://localhost:{port}')
    asyncio.get_event_loop().run_forever()