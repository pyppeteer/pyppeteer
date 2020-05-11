import asyncio
import logging
import mimetypes
from contextlib import suppress
from pathlib import Path
from urllib.parse import urljoin

import pytest
from pyppeteer import Browser, launch
from pyppeteer.browser import BrowserContext
from pyppeteer.errors import PageError
from pyppeteer.page import Page
from pyppeteer.util import get_free_port
from syncer import sync
from tests.utils.golden import golden_comparators
from tests.utils.server import WrappedApplication, app_runner
from websockets import ConnectionClosedError

# internal, conftest.py only variables
_launch_options = {'args': ['--no-sandbox']}
_firefox = False
_port = get_free_port()

if _firefox:
    _launch_options['product'] = 'firefox'

CHROME = not _firefox


def pytest_configure(config):
    # shim for running in pycharm - see https://youtrack.jetbrains.com/issue/PY-41295
    # this is useful when debugging tests that hang, preventing the PyCharm pytest runner
    # from displaying the captured log calls
    if config.getoption('--verbose'):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[{levelname}] {name}: {message}', style='{'))
        logging.getLogger('pyppeteer').addHandler(handler)


class ServerURL:
    def __init__(self, port, app, cross_process: bool = False, https: bool = False, child_instance: bool = False):
        self.app: WrappedApplication = app
        # https will be at port+1
        self.port = port + int(https)
        del port  # make sure we always refer to updated port
        self.base = f'http{"s" if https else ""}://{"127.0.0.1" if cross_process else "localhost"}:{self.port}'
        if not child_instance:
            if not https:
                self.https = ServerURL(self.port, app, https=True, child_instance=True)
            if not cross_process:
                self.cross_process_server = ServerURL(self.port, app, cross_process=True, child_instance=True)

        else:
            self.https = None
            self.cross_process_server = None

        self.empty_page = self / 'empty.html'

    def __repr__(self):
        return f'<ServerURL "{self.base}">'

    def __truediv__(self, other):
        """allows you to do stuff like ServerURL / 'button.html' which becomes 'http://localhost:453/button.html'"""
        return urljoin(self.base, other)


@pytest.fixture(scope='session')
def test_dir():
    return Path(__file__).parent


@pytest.fixture(scope='session')
def assets(test_dir):
    return test_dir / 'assets'


@pytest.fixture(scope='session')
def golden_chrome_dir(test_dir):
    return test_dir / 'golden-chromium'


@pytest.fixture(scope='session')
def golden_firefox_dir(test_dir):
    return test_dir / 'golden-firefox'


@pytest.fixture(scope='session')
def isGolden(golden_chrome_dir, golden_firefox_dir, firefox):
    def comparer(input_bytes_or_str, actual_file_name):
        read_fn = 'read_bytes' if isinstance(input_bytes_or_str, bytes) else 'read_text'
        if firefox:
            gdir = golden_firefox_dir
        else:
            gdir = golden_chrome_dir
        output_file = gdir / actual_file_name
        if not output_file.exists():
            raise FileNotFoundError(f'{actual_file_name} does not exist in the golden directory! (dir={output_file})')

        mime_type = mimetypes.guess_type(output_file)[0]
        try:
            comparator = golden_comparators[mime_type]
        except KeyError:
            raise KeyError(f'No comparator known for mime type "{mime_type}"')

        if isinstance(input_bytes_or_str, bytes):
            result = comparator(input_bytes_or_str, output_file.read_bytes())
        else:
            result = comparator(input_bytes_or_str, output_file.read_text())

        if not result:
            return True

        if result.get('diff'):
            diff_path = None
        if result.get('error'):
            raise AssertionError(f'golden mismatch for {actual_file_name}: {result["error"]}')

        return True

    return comparer


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
def server(assets):
    app = sync(app_runner(assets_path=assets, free_port=_port))
    yield ServerURL(_port, app)
    sync(app.shutdown())
    sync(app.cleanup())


@pytest.fixture(scope='session')
def firefox():
    return _firefox


@pytest.fixture(scope='session')
def event_loop():
    return asyncio.get_event_loop()


chrome_only = pytest.mark.skipif(_firefox, reason='Test fails under firefox, or is not implemented for it')
needs_server_side_implementation = pytest.mark.skip(reason='Needs server side implementation')
