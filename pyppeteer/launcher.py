#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium process launcher module."""

import atexit
import logging
import os
import os.path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, TYPE_CHECKING

from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.util import check_chromium, chromium_excutable
from pyppeteer.util import download_chromium

if TYPE_CHECKING:
    from typing import Optional  # noqa: F401

logger = logging.getLogger(__name__)

pyppeteer_home = os.path.join(os.path.expanduser('~'), '.pyppeteer')
CHROME_PROFILIE_PATH = os.path.join(pyppeteer_home, '.dev_profile')

DEFAULT_ARGS = [
    '--disable-background-networking',
    '--disable-background-timer-throttling',
    '--disable-client-side-phishing-detection',
    '--disable-default-apps',
    '--disable-hang-monitor',
    '--disable-popup-blocking',
    '--disable-prompt-on-repost',
    '--disable-sync',
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
        user_data_dir = None
        if isinstance(self.options.get('args'), list):
            user_data_dir_arg = '--user-data-dir='
            for index, arg in enumerate(self.options['args']):
                if arg.startswith(user_data_dir_arg):
                    user_data_dir = arg.split(user_data_dir_arg)[1]
                    break
            self.chrome_args = self.chrome_args + self.options['args']
        if user_data_dir is None:
            if not os.path.exists(CHROME_PROFILIE_PATH):
                os.mkdir(CHROME_PROFILIE_PATH)
            self._tmp_user_data_dir = tempfile.mkdtemp(
                dir=CHROME_PROFILIE_PATH)
            self.chrome_args = self.chrome_args + [
                '--user-data-dir=' + self._tmp_user_data_dir,
            ]

    def launch(self) -> Browser:
        """Start chromium process."""
        self.proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        atexit.register(self.killChrome)
        import time
        while True:
            time.sleep(0.1)
            msg = self.proc.stdout.readline().decode()
            if not msg:
                continue
            m = re.match(r'DevTools listening on (ws://.*)$', msg)
            if m is not None:
                break
        logger.debug(m.group(0))
        self.url = m.group(1).strip()
        connectionDelay = self.options.get('slowMo', 0)
        connection = Connection(self.url, connectionDelay)
        return Browser(connection,
                       self.options.get('ignoreHTTPSErrors', False),
                       self.killChrome)

    def killChrome(self) -> None:
        """Terminate chromium process."""
        logger.debug('terminate chrome process...')
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait()
            logger.debug('done.')
        if self._tmp_user_data_dir and os.path.exists(self._tmp_user_data_dir):
            shutil.rmtree(self._tmp_user_data_dir)

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
