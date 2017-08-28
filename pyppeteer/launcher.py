#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

logger = logging.getLogger(__name__)

rootdir = Path(__file__).resolve().parent.parent
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
    def __init__(self, options: Dict[str, Any] = None) -> None:
        global BROWSER_ID
        BROWSER_ID += 1
        self.options = options or dict()
        self.user_data_dir = CHROME_PROFILIE_PATH / str(os.getpid()) / str(BROWSER_ID)  # noqa: E501
        self.chrome_args = DEFAULT_ARGS + [
            '--user-data-dir=' + shlex.quote(str(self.user_data_dir)),
        ]
        if 'headless' not in self.options or self.options.get('headless'):
            self.chrome_args = self.chrome_args + [
                '--headless',
                '--disable-gpu',
                '--hide-scrollbars',
                '--mute-audio',
            ]
        self.exec = str(rootdir / 'chrome')
        self.cmd = [self.exec] + self.chrome_args

    def launch(self, options: dict = None) -> Browser:
        if options is None:
            options = dict()
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
        connectionDelay = options.get('slowMo', 0)
        connection = Connection(self.url, connectionDelay)
        return Browser(connection, options.get('ignoreHTTPSErrors'),
                       self.killChrome)

    def killChrome(self) -> None:
        logger.debug('terminate chrome process...')
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait()
            logger.debug('done.')

    async def connect(self, browserWSEndpoint: str,
                      ignoreHTTPSErrors: bool = False) -> Browser:
        connection = await Connection.create(browserWSEndpoint)
        return Browser(connection, bool(ignoreHTTPSErrors), self.killChrome)


def launch(options: dict = None) -> Browser:
    return Launcher(options).launch()


def connect(options: dict = None) -> Browser:
    l = Launcher(options)
    return l.connect()
