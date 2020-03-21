import pytest
from syncer import sync

from pyppeteer import launch, Browser
from pyppeteer.browser import BrowserContext
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
def isolated_page(shared_browser) -> Page:
    page = sync(shared_browser.newPage())
    yield page
    sync(page.close())


@pytest.fixture
def isolated_context(shared_browser) -> BrowserContext:
    ctx = sync(shared_browser.createIncognitoBrowserContext())
    yield ctx
    sync(ctx.close())


@pytest.fixture(scope='session')
def server():
    port = get_free_port()
    app = get_application()
    server = app.listen(port)
    yield server
    sync(server.stop)


chrome_only = pytest.mark.skipif(firefox)
