from typing import Generator

import pytest
from syncer import sync

from pyppeteer import launch, Browser
from pyppeteer.page import Page

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
def isolated_page(shared_browser) -> Generator[Page, None, None]:
    page = sync(shared_browser.newPage())
    yield page
    sync(page.close())


chrome_only = pytest.mark.skipif(firefox)

