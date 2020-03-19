from typing import Generator

import pytest
from syncer import sync

from pyppeteer import launch, Browser
from pyppeteer.page import Page

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}


@pytest.fixture(scope='session')
def browser() -> Browser:
    return sync(launch(args='--no-sandbox'))


@pytest.fixture
def isolated_page() -> Generator[Page, None, None]:
    page = sync(browser.newPage())
    yield page
    sync(page.close())
