import pytest
from syncer import sync

from pyppeteer import launch

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}


@pytest.fixture(scope='session')
def browser():
    return sync(launch(args='--no-sandbox'))


@pytest.fixture
def isolated_page():
    page = sync(browser.newPage())
    yield page
    sync(page.close())
