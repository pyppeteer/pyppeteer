#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium process launcher module."""

import asyncio
import atexit
import json
from urllib.request import urlopen
from urllib.error import URLError
import logging
import os
import os.path
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, TYPE_CHECKING

from pyppeteer import __pyppeteer_home__
from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.helper import addEventListener, debugError, removeEventListeners
from pyppeteer.target import Target
from pyppeteer.util import check_chromium, chromium_executable
from pyppeteer.util import download_chromium, merge_dict, get_free_port

if TYPE_CHECKING:
    from typing import Optional  # noqa: F401

logger = logging.getLogger(__name__)

pyppeteer_home = Path(__pyppeteer_home__)
CHROME_PROFILE_PATH = pyppeteer_home / '.dev_profile'

DEFAULT_ARGS = [
    '--disable-background-networking',
    '--disable-background-timer-throttling',
    '--disable-breakpad',
    '--disable-browser-side-navigation',
    '--disable-client-side-phishing-detection',
    '--disable-default-apps',
    '--disable-dev-shm-usage',
    '--disable-extensions',
    '--disable-features=site-per-process',
    '--disable-hang-monitor',
    '--disable-popup-blocking',
    '--disable-prompt-on-repost',
    '--disable-sync',
    '--disable-translate',
    '--metrics-recording-only',
    '--no-first-run',
    '--safebrowsing-disable-auto-update',
]

AUTOMATION_ARGS = [
    '--enable-automation',
    '--password-store=basic',
    '--use-mock-keychain',
]


class Launcher(object):
    """Chrome process launcher class."""

    def __init__(self, options: Dict[str, Any] = None,  # noqa: C901
                 **kwargs: Any) -> None:
        """Make new launcher."""
        self.options = merge_dict(options, kwargs)
        self.port = get_free_port()
        self.url = f'http://127.0.0.1:{self.port}'
        self.chrome_args: List[str] = []
        self._loop = self.options.get('loop', asyncio.get_event_loop())

        logLevel = self.options.get('logLevel')
        if logLevel:
            logging.getLogger('pyppeteer').setLevel(logLevel)

        if not self.options.get('ignoreDefaultArgs', False):
            self.chrome_args.extend(DEFAULT_ARGS)
            self.chrome_args.append(
                f'--remote-debugging-port={self.port}',
            )

        self.chromeClosed = True
        if self.options.get('appMode', False):
            self.options['headless'] = False
        elif not self.options.get('ignoreDefaultArgs', False):
            self.chrome_args.extend(AUTOMATION_ARGS)

        self._tmp_user_data_dir: Optional[str] = None
        self._parse_args()

        if self.options.get('devtools'):
            self.chrome_args.append('--auto-open-devtools-for-tabs')
            self.options['headless'] = False

        if 'headless' not in self.options or self.options.get('headless'):
            self.chrome_args.extend([
                '--headless',
                '--disable-gpu',
                '--hide-scrollbars',
                '--mute-audio',
            ])

        def _is_default_url() -> bool:
            for arg in self.options['args']:
                if not arg.startswith('-'):
                    return False
            return True

        if (not self.options.get('ignoreDefaultArgs') and
                isinstance(self.options.get('args'), list) and
                _is_default_url()):
            self.chrome_args.append('about:blank')

        if 'executablePath' in self.options:
            self.exec = self.options['executablePath']
        else:
            if not check_chromium():
                download_chromium()
            self.exec = str(chromium_executable())

        self.cmd = [self.exec] + self.chrome_args

    def _parse_args(self) -> None:
        if (not isinstance(self.options.get('args'), list) or
                not any(opt for opt in self.options['args']
                        if opt.startswith('--user-data-dir'))):
            if 'userDataDir' not in self.options:
                if not CHROME_PROFILE_PATH.exists():
                    CHROME_PROFILE_PATH.mkdir(parents=True)
                self._tmp_user_data_dir = tempfile.mkdtemp(
                    dir=str(CHROME_PROFILE_PATH))
            self.chrome_args.append('--user-data-dir={}'.format(
                self.options.get('userDataDir', self._tmp_user_data_dir)))
        if isinstance(self.options.get('args'), list):
            self.chrome_args.extend(self.options['args'])

    def _cleanup_tmp_user_data_dir(self) -> None:
        for retry in range(100):
            if self._tmp_user_data_dir and os.path.exists(
                    self._tmp_user_data_dir):
                shutil.rmtree(self._tmp_user_data_dir, ignore_errors=True)
                if os.path.exists(self._tmp_user_data_dir):
                    time.sleep(0.01)
            else:
                break
        else:
            raise IOError('Unable to remove Temporary User Data')

    async def launch(self) -> Browser:  # noqa: C901
        """Start chrome process and return `Browser` object."""
        self.chromeClosed = False
        self.connection: Optional[Connection] = None

        options = dict()
        options['env'] = self.options.get('env')
        if not self.options.get('dumpio'):
            options['stdout'] = subprocess.PIPE
            options['stderr'] = subprocess.STDOUT

        self.proc = subprocess.Popen(  # type: ignore
            self.cmd,
            **options,
        )

        def _close_process(*args: Any, **kwargs: Any) -> None:
            if not self.chromeClosed:
                self._loop.run_until_complete(self.killChrome())

        # don't forget to close browser process
        if self.options.get('autoClose', True):
            atexit.register(_close_process)
        if self.options.get('handleSIGINT', True):
            signal.signal(signal.SIGINT, _close_process)
        if self.options.get('handleSIGTERM', True):
            signal.signal(signal.SIGTERM, _close_process)
        if not sys.platform.startswith('win'):
            # SIGHUP is not defined on windows
            if self.options.get('handleSIGHUP', True):
                signal.signal(signal.SIGHUP, _close_process)

        connectionDelay = self.options.get('slowMo', 0)
        self.browserWSEndpoint = self._get_ws_endpoint()
        logger.info(f'Browser listening on: {self.browserWSEndpoint}')
        self.connection = Connection(
            self.browserWSEndpoint, self._loop, connectionDelay)
        ignoreHTTPSErrors = bool(self.options.get('ignoreHTTPSErrors', False))
        setDefaultViewport = not self.options.get('appMode', False)
        browser = await Browser.create(
            self.connection, [], ignoreHTTPSErrors, setDefaultViewport,
            self.proc, self.killChrome)
        await self.ensureInitialPage(browser)
        return browser

    async def ensureInitialPage(self, browser: Browser) -> None:
        """Wait for initial page target to be created."""
        for target in browser.targets():
            if target.type == 'page':
                return

        initialPagePromise = self._loop.create_future()

        def initialPageCallback() -> None:
            initialPagePromise.set_result(True)

        def check_target(target: Target) -> None:
            if target.type == 'page':
                initialPageCallback()

        listeners = [addEventListener(browser, 'targetcreated', check_target)]
        await initialPagePromise
        removeEventListeners(listeners)

    def _get_ws_endpoint(self) -> str:
        url = self.url + '/json/version'
        while self.proc.poll() is None:
            time.sleep(0.1)
            try:
                with urlopen(url) as f:
                    data = json.loads(f.read().decode())
                break
            except URLError as e:
                continue
        else:
            raise BrowserError(
                'Browser closed unexpectedly:\n{}'.format(
                    self.proc.stdout.read().decode()
                )
            )
        return data['webSocketDebuggerUrl']

    def waitForChromeToClose(self) -> None:
        """Terminate chrome."""
        if self.proc.poll() is None and not self.chromeClosed:
            self.chromeClosed = True
            try:
                self.proc.terminate()
                self.proc.wait()
            except Exception:
                # browser process may be already closed
                pass

    async def killChrome(self) -> None:
        """Terminate chromium process."""
        logger.info('terminate chrome process...')
        if self.connection and self.connection._connected:
            try:
                await self.connection.send('Browser.close')
                await self.connection.dispose()
            except Exception as e:
                # ignore errors on browser termination process
                debugError(logger, e)
        if self._tmp_user_data_dir and os.path.exists(self._tmp_user_data_dir):
            # Force kill chrome only when using temporary userDataDir
            self.waitForChromeToClose()
            self._cleanup_tmp_user_data_dir()


async def launch(options: dict = None, **kwargs: Any) -> Browser:
    """Start chrome process and return :class:`~pyppeteer.browser.Browser`.

    This function is a shortcut to :meth:`Launcher(options, **kwargs).launch`.

    Available options are:

    * ``ignoreHTTPSErrors`` (bool): Whether to ignore HTTPS errors. Defaults to
      ``False``.
    * ``headless`` (bool): Whether to run browser in headless mode. Defaults to
      ``True`` unless ``appMode`` or ``devtools`` options is ``True``.
    * ``executablePath`` (str): Path to a Chromium or Chrome executable to run
      instead of default bundled Chromium.
    * ``slowMo`` (int|float): Slow down pyppeteer operations by the specified
      amount of milliseconds.
    * ``args`` (List[str]): Additional arguments (flags) to pass to the browser
      process.
    * ``ignoreDefaultArgs`` (bool): Do not use pyppeteer's default args. This
      is dangerous option; use with care.
    * ``handleSIGINT`` (bool): Close the browser process on Ctrl+C. Defaults to
      ``True``.
    * ``handleSIGTERM`` (bool): Close the browser process on SIGTERM. Defaults
      to ``True``.
    * ``handleSIGHUP`` (bool): Close the browser process on SIGHUP. Defaults to
      ``True``.
    * ``dumpio`` (bool): Whether to pipe the browser process stdout and stderr
      into ``process.stdout`` and ``process.stderr``. Defaults to ``False``.
    * ``userDataDir`` (str): Path to a user data directory.
    * ``env`` (dict): Specify environment variables that will be visible to the
      browser. Defaults to same as python process.
    * ``devtools`` (bool): Whether to auto-open a DevTools panel for each tab.
      If this option is ``True``, the ``headless`` option will be set
      ``False``.
    * ``logLevel`` (int|str): Log level to print logs. Defaults to same as the
      root logger.
    * ``autoClose`` (bool): Automatically close browser process when script
      completed. Defaults to ``True``.
    * ``loop`` (asyncio.AbstractEventLoop): Event loop (**experimental**).
    * ``appMode`` (bool): Deprecated.

    .. note::
        Pyppeteer can also be used to control the Chrome browser, but it works
        best with the version of Chromium it is bundled with. There is no
        guarantee it will work with any other version. Use ``executablePath``
        option with extreme caution.
    """
    return await Launcher(options, **kwargs).launch()


async def connect(options: dict = None, **kwargs: Any) -> Browser:
    """Connect to the existing chrome.

    ``browserWSEndpoint`` option is necessary to connect to the chrome. The
    format is ``ws://${host}:${port}/devtools/browser/<id>``. This value can
    get by :attr:`~pyppeteer.browser.Browser.wsEndpoint`.

    Available options are:

    * ``browserWSEndpoint`` (str): A browser websocket endpoint to connect to.
      (**required**)
    * ``ignoreHTTPSErrors`` (bool): Whether to ignore HTTPS errors. Defaults to
      ``False``.
    * ``slowMo`` (int|float): Slow down pyppeteer's by the specified amount of
      milliseconds.
    * ``logLevel`` (int|str): Log level to print logs. Defaults to same as the
      root logger.
    * ``loop`` (asyncio.AbstractEventLoop): Event loop (**experimental**).
    """
    options = merge_dict(options, kwargs)
    logLevel = options.get('logLevel')
    if logLevel:
        logging.getLogger('pyppeteer').setLevel(logLevel)

    browserWSEndpoint = options.get('browserWSEndpoint')
    if not browserWSEndpoint:
        raise BrowserError('Need `browserWSEndpoint` option.')
    connectionDelay = options.get('slowMo', 0)
    connection = Connection(browserWSEndpoint,
                            options.get('loop', asyncio.get_event_loop()),
                            connectionDelay)
    browserContextIds = (await connection.send('Target.getBrowserContexts')
                         ).get('browserContextIds', [])
    ignoreHTTPSErrors = bool(options.get('ignoreHTTPSErrors', False))
    return await Browser.create(
        connection, browserContextIds, ignoreHTTPSErrors, True, None,
        lambda: connection.send('Browser.close'))


def executablePath() -> str:
    """Get executable path of default chrome."""
    return str(chromium_executable())


def defaultArgs() -> List[str]:
    """Get list of default chrome args."""
    return DEFAULT_ARGS + AUTOMATION_ARGS
