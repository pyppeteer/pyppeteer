#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium process launcher module."""

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
    '--disable-client-side-phishing-detection',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-hang-monitor',
    '--disable-popup-blocking',
    '--disable-prompt-on-repost',
    '--disable-sync',
    '--disable-translate',
    '--enable-automation',
    '--metrics-recording-only',
    '--no-first-run',
    '--password-store=basic',
    '--remote-debugging-port=0',
    '--safebrowsing-disable-auto-update',
    '--use-mock-keychain',
]


class Launcher(object):
    """Chromium parocess launcher class."""

    def __init__(self, options: Dict[str, Any] = None, **kwargs: Any) -> None:
        """Make new launcher."""
        self.options = options or dict()
        self.options.update(kwargs)
        self.chrome_args = DEFAULT_ARGS
        self._tmp_user_data_dir: Optional[str] = None
        self._parse_args()
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
                # maybe better after register(self.killChrome)
                atexit.register(self._cleanup_tmp_user_data_dir)
            self.chrome_args.append('--user-data-dir={}'.format(
                self.options.get('userDataDir', self._tmp_user_data_dir)))
        if isinstance(self.options.get('args'), list):
            self.chrome_args.extend(self.options['args'])

    def _cleanup_tmp_user_data_dir(self) -> None:
        if self._tmp_user_data_dir and os.path.exists(self._tmp_user_data_dir):
            shutil.rmtree(self._tmp_user_data_dir)

    def launch(self) -> Browser:
        """Start chromium process."""
        self.proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        atexit.register(self.killChrome)
        import time
        for _ in range(100):
            # wait for DevTools port to open for at least 10sec
            # setting timeout timer is bettter
            time.sleep(0.1)
            if self.proc.poll() is not None:
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
        connection = Connection(m.group(1).strip(), connectionDelay)
        return Browser(connection,
                       self.options.get('ignoreHTTPSErrors', False),
                       self.killChrome)

    def killChrome(self) -> None:
        """Terminate chromium process."""
        logger.debug('terminate chrome process...')
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait()

    async def connect(self, browserWSEndpoint: str,
                      ignoreHTTPSErrors: bool = False) -> Browser:
        """Not Implemented."""
        raise NotImplementedError('NotImplemented')
        # connection = await Connection.create(browserWSEndpoint)
        # return Browser(connection, bool(ignoreHTTPSErrors), self.killChrome)


def launch(options: dict = None, **kwargs: Any) -> Browser:
    """Start chromium process and return `Browser` object."""
    return Launcher(options, **kwargs).launch()


def connect(options: dict = None) -> Browser:
    """Not Implemented."""
    raise NotImplementedError('NotImplemented')
    # l = Launcher(options)
    # return l.connect()


def executablePath() -> str:
    """Get executable path of chromium."""
    return str(chromium_excutable())
