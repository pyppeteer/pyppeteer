import asyncio

import pytest
from syncer import sync

from pyppeteer import launch, Browser
from pyppeteer.browser import BrowserContext
from pyppeteer.errors import PageError
from pyppeteer.page import Page
from pyppeteer.util import get_free_port
from tests.server import get_application

firefox = False
launch_options = {'args': ['--no-sandbox']}

if firefox:
    launch_options['product'] = 'firefox'

_browser: Browser = sync(launch(**launch_options))


@pytest.fixture(scope='session')
def shared_browser() -> Browser:
    yield _browser
    sync(_browser.close())


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
def _app():
    return get_application()


@pytest.fixture(scope='session')
def _port():
    return get_free_port()


@pytest.fixture(scope='session')
def server_url(_port):
    return f'http://localhost:{_port}'


@pytest.fixture(scope='session')
def server(_app, _port):
    server = _app.listen(_port)
    yield server
    sync(server.stop)

@pytest.fixture(scope='session')
def firefox():
    return firefox

@pytest.fixture(scope='session')
def event_loop():
    return asyncio.get_event_loop()

chrome_only = pytest.mark.skipif(firefox)
