#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium process launcher module."""

import asyncio
import atexit
import logging
import os
import os.path
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, TYPE_CHECKING

from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.util import check_chromium, chromium_excutable
from pyppeteer.util import download_chromium

if TYPE_CHECKING:
    from typing import Optional  # noqa: F401

logger = logging.getLogger(__name__)

pyppeteer_home = Path.home() / '.pyppeteer'
CHROME_PROFILIE_PATH = pyppeteer_home / '.dev_profile'

DEFAULT_ARGS = [
    '--disable-background-networking',
    '--disable-background-timer-throttling',
    '--disable-browser-side-navigation',
    '--disable-client-side-phishing-detection',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-hang-monitor',
    '--disable-popup-blocking',
    '--disable-prompt-on-repost',
    '--disable-sync',
    '--disable-translate',
    '--metrics-recording-only',
    '--no-first-run',
    '--remote-debugging-port=0',
    '--safebrowsing-disable-auto-update',
]

AUTOMATION_ARGS = [
    '--enable-automation',
    '--password-store=basic',
    '--use-mock-keychain',
]


class Launcher(object):
    """Chromium parocess launcher class."""

    def __init__(self, options: Dict[str, Any] = None, **kwargs: Any) -> None:
        """Make new launcher."""
        self.options: Dict = {}
        if options:
            self.options.update(options)
        self.options.update(kwargs)
        self.chrome_args = DEFAULT_ARGS
        self.chromeClosed = True
        if self.options.get('appMode', False):
            self.options['headless'] = False
        else:
            self.chrome_args.extend(AUTOMATION_ARGS)

        self._tmp_user_data_dir: Optional[str] = None
        self._parse_args()

        if self.options.get('devtools'):
            self.chrome_args.append('--auto-open-devtools-for-tabs')
            self.options['headless'] = False

        if 'headless' not in self.options or self.options.get('headless'):
            self.chrome_args = self.chrome_args + [
                '--headless',
                '--disable-gpu',
                '--hide-scrollbars',
                '--mute-audio',
            ]
        if 'executablePath' in self.options:
            self.exec = self.options['executablePath']
        else:
            if not check_chromium():
                download_chromium()
            self.exec = str(chromium_excutable())
        self.cmd = [self.exec] + self.chrome_args

    def _parse_args(self) -> None:
        if (not isinstance(self.options.get('args'), list) or
                not any(opt for opt in self.options['args']
                        if opt.startswith('--user-data-dir'))):
            if 'userDataDir' not in self.options:
                if not CHROME_PROFILIE_PATH.exists():
                    CHROME_PROFILIE_PATH.mkdir(parents=True)
                self._tmp_user_data_dir = tempfile.mkdtemp(
                    dir=str(CHROME_PROFILIE_PATH))
            self.chrome_args.append('--user-data-dir={}'.format(
                self.options.get('userDataDir', self._tmp_user_data_dir)))
        if isinstance(self.options.get('args'), list):
            self.chrome_args.extend(self.options['args'])

    def _cleanup_tmp_user_data_dir(self) -> None:
        if self._tmp_user_data_dir and os.path.exists(self._tmp_user_data_dir):
            shutil.rmtree(self._tmp_user_data_dir)

    def launch(self) -> Browser:
        """Start chromium process."""
        env = self.options.get('env', {})
        self.chromeClosed = False
        self.connection: Optional[Connection] = None
        self.proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )

        def _close_process() -> None:
            asyncio.get_event_loop().run_until_complete(self.killChrome())

        # dont forget to close browser process
        atexit.register(_close_process)

        import time
        for _ in range(100):
            # wait for DevTools port to open for at least 10sec
            # setting timeout timer is bettter
            time.sleep(0.1)
            if self.proc.poll() is not None:
                self._cleanup_tmp_user_data_dir()
                raise BrowserError('Unexpectedly chrome process closed with '
                                   f'return code: {self.proc.returncode}')
            msg = self.proc.stdout.readline().decode()
            if not msg:
                continue
            m = re.match(r'DevTools listening on (ws://.*)$', msg)
            if m is not None:
                break
        else:
            # This block called only when `for`-loop does not `break`
            raise BrowserError('Failed to connect DevTools port.')
        logger.debug(m.group(0))
        connectionDelay = self.options.get('slowMo', 0)
        self.browserWSEndpoint = m.group(1).strip()
        self.connection = Connection(self.browserWSEndpoint, connectionDelay)
        return Browser(self.connection, self.options, self.killChrome)

    def waitForChromeToClose(self) -> None:
        """Terminate chrome."""
        if self.proc.poll() is None and not self.chromeClosed:
            self.chromeClosed = True
            self.proc.terminate()
            self.proc.wait()
            self._cleanup_tmp_user_data_dir()

    async def killChrome(self) -> None:
        """Terminate chromium process."""
        logger.debug('terminate chrome process...')
        if self._tmp_user_data_dir and os.path.exists(self._tmp_user_data_dir):
            self.waitForChromeToClose()
        else:
            if self.connection:
                await self.connection.send('Browser.close')


def launch(options: dict = None, **kwargs: Any) -> Browser:
    """Start chromium process and return `Browser` object."""
    return Launcher(options, **kwargs).launch()


def connect(options: dict = None, **kwargs: Any) -> Browser:
    """Connect to existing chrome."""
    if options is None:
        options = {}
    options.update(kwargs)
    browserWSEndpoint = options.get('browserWSEndpoint')
    if not browserWSEndpoint:
        raise BrowserError('Need `browserWSEndpoint` option.')
    connection = Connection(browserWSEndpoint)
    return Browser(
        connection, options, lambda: connection.send('Browser.close'))


def executablePath() -> str:
    """Get executable path of chromium."""
    return str(chromium_excutable())
