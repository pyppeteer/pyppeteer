import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from urllib.parse import urljoin

import pytest
from syncer import sync
from websockets import ConnectionClosedError

from pyppeteer import launch, Browser
from pyppeteer.browser import BrowserContext
from pyppeteer.errors import PageError
from pyppeteer.page import Page
from pyppeteer.util import get_free_port
from tests.server import get_application, _Application

# internal, conftest.py only variables
_launch_options = {'args': ['--no-sandbox']}
_firefox = False
_app = get_application()
_port = get_free_port()

if _firefox:
    _launch_options['product'] = 'firefox'


def pytest_configure(config):
    # shim for running in pycharm - see https://youtrack.jetbrains.com/issue/PY-41295
    if config.getoption('--verbose'):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[{levelname}] {name}: {message}', style='{'))
        logging.getLogger('pyppeteer').addHandler(handler)


class ServerURL:
    def __init__(self, port, app, cross_process: bool = False, https: bool = False, child_inst: bool = False):
        self.app: _Application = app
        self.base = f'http{"s" if https else ""}://{"127.0.0.1" if cross_process else "localhost"}:{port}'
        if not child_inst:
            self.https = ServerURL(port, app, https=True, child_inst=True)
            self.cross_process_server = ServerURL(port, app, cross_process=True, child_inst=True)
        self.empty_page = self / 'empty.html'

    def __repr__(self):
        return f'<ServerURL "{self.base}">'

    def __truediv__(self, other):
        return urljoin(self.base, other)


@pytest.fixture(scope='session')
def assets():
    return Path(__file__).parent / 'assets'


@pytest.fixture(scope='session')
def shared_browser() -> Browser:
    browser = sync(launch(**_launch_options))
    yield browser
    # we don't care if we interrupt the websocket connection
    with suppress(ConnectionClosedError):
        sync(browser.close())


@pytest.fixture
def isolated_context(shared_browser) -> BrowserContext:
    ctx = sync(shared_browser.createIncognitoBrowserContext())
    yield ctx
    with suppress(ConnectionError):
        sync(ctx.close())


@pytest.fixture
def isolated_page(isolated_context) -> Page:
    page = sync(isolated_context.newPage())
    yield page
    with suppress(PageError):
        sync(page.close())


@pytest.fixture(scope='session')
def server():
    _server = _app.listen(_port)
    yield ServerURL(_port, _app)
    _server.stop()


@pytest.fixture(scope='session')
def firefox():
    return _firefox


@pytest.fixture(scope='session')
def event_loop():
    return asyncio.get_event_loop()


chrome_only = pytest.mark.skipif(_firefox, reason='Test fails under firefox, or is not implemented for it')
needs_server_side_implementation = pytest.mark.skip(reason='Needs server side implementation')