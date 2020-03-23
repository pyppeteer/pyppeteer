import asyncio

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


@pytest.fixture(scope='session')
def shared_browser() -> Browser:
    browser = sync(launch(**_launch_options))
    yield browser
    sync(browser.close())


@pytest.fixture
def isolated_context(shared_browser) -> BrowserContext:
    ctx = sync(shared_browser.createIncognitoBrowserContext())
    yield ctx
    sync(ctx.close())


@pytest.fixture
def isolated_page(isolated_context) -> Page:
    page = sync(isolated_context.newPage())
    yield page
    try:
        sync(page.close())
    except PageError as e:
        if 'page has been closed' not in str(e):
            raise e


@pytest.fixture(scope='session')
def server_url(server):
    return f'http://localhost:{_port}'


@pytest.fixture(scope='session')
def server_url_empty_page(server_url) -> str:
    return f'{server_url}/empty.html'


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
