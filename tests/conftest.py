import asyncio
import logging
from contextlib import suppress
from urllib.parse import urljoin

import pytest
from syncer import sync

from pyppeteer import launch, Browser
from pyppeteer.browser import BrowserContext
from pyppeteer.errors import PageError
from pyppeteer.page import Page
from pyppeteer.util import get_free_port
from tests.server import get_application

# internal, conftest.py only variables
_launch_options = {'args': ['--no-sandbox']}
_firefox = False
_app = get_application()
_port = get_free_port()

if _firefox:
    _launch_options['product'] = 'firefox'


class ServerURL:
    def __init__(self, base):
        self.base = base
        self.empty_page = self / 'empty.html'

    def __repr__(self):
        return f'<ServerURL "{self.base}">'

    def __truediv__(self, other):
        return urljoin(self.base, other)


@pytest.fixture(scope='session')
def shared_browser() -> Browser:
    browser = sync(launch(**_launch_options))
    yield browser
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
def server_url(server):
    return ServerURL(f'http://localhost:{_port}')


@pytest.fixture(scope='session')
def server():
    _server = _app.listen(_port)
    yield _server
    _server.stop()


@pytest.fixture(scope='session')
def firefox():
    return _firefox


@pytest.fixture(scope='session')
def event_loop():
    return asyncio.get_event_loop()


chrome_only = pytest.mark.skipif(_firefox)
