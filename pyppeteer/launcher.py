#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium process launcher module."""

import atexit
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Dict

from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.util import check_chromium, chromium_excutable
from pyppeteer.util import download_chromium

logger = logging.getLogger(__name__)

rootdir = Path.home() / '.pyppeteer'
CHROME_PROFILIE_PATH = rootdir / '.dev_profile'
BROWSER_ID = 0

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
        global BROWSER_ID
        BROWSER_ID += 1
        self.options = options or dict()
        self.options.update(kwargs)
        self.chrome_args = DEFAULT_ARGS
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
        if isinstance(self.options.get('args'), list):
            user_data_dir_arg = '--user-data-dir='
            for index, arg in enumerate(self.options['args']):
                if arg.startswith(user_data_dir_arg):
                    self.user_data_dir = Path(arg.split(user_data_dir_arg)[1])
                    break
            self.chrome_args = self.chrome_args + self.options['args']
        if not hasattr(self, 'user_data_dir'):
            self.user_data_dir = (CHROME_PROFILIE_PATH / str(os.getpid()) /
                                  str(BROWSER_ID))
            self.chrome_args = self.chrome_args + [
                '--user-data-dir=' + shlex.quote(str(self.user_data_dir)),
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
