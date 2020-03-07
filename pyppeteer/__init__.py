#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta data for pyppeteer."""

import logging
import os

from appdirs import AppDirs

__author__ = """Hiroyuki Takagi"""
__email__ = 'pyppeteer@protonmail.com'
__version__ = '0.2.2'
__chromium_revision__ = '743021'  # 2020-02-20
# __chromium_revision__ = '588429'
__base_puppeteer_version__ = 'v1.6.0'
__pyppeteer_home__ = os.environ.get('PYPPETEER_HOME', AppDirs('pyppeteer').user_data_dir)  # type: str
DEBUG = False

# Setup root logger
_logger = logging.getLogger('pyppeteer')
_log_handler = logging.StreamHandler()
_fmt = '[{levelname[0]}:{name}] {msg}'
_formatter = logging.Formatter(fmt=_fmt, style='{')
_log_handler.setFormatter(_formatter)
_log_handler.setLevel(logging.DEBUG)
_logger.addHandler(_log_handler)
_logger.propagate = False

from typing import Dict, Any

from pyppeteer.browser import Browser
from pyppeteer.device_descriptors import devices
from pyppeteer.launcher import launcher
from pyppeteer.browser_fetcher import BrowserFetcher


class Pyppeteer:
    def __init__(self, projectRoot: str, preferredRevision: str):
        self._projectRoot = projectRoot
        self._preferredRevision = preferredRevision
        self._lazyLauncher = None
        self.productName = None

    @property
    def executablePath(self):
        return self._launcher.executablePath

    @property
    def product(self):
        return self._launcher.product

    @property
    def devices(self):
        return devices

    async def launch(self, options: Dict[str, Any] = None) -> Browser:
        if not self.productName and options:
            self.productName = options.get('product')
        return await self._launcher.launch(options)

    def connect(self, options: Any):
        return self._launcher.connect(options)

    @property
    def _launcher(self):
        if not self._lazyLauncher:
            self._lazyLauncher = launcher(
                projectRoot=self._projectRoot, preferredRevision=self._preferredRevision, product=self.productName
            )
        return self._lazyLauncher

    async def defaultArgs(self, options: Any):
        return self._launcher.defaultArgs(options)

    def createBrowserFetcher(self, options: Any):
        return BrowserFetcher(projectRoot=self._projectRoot, options=options)


version = __version__
version_info = tuple(int(i) for i in version.split('.'))

__all__ = [
    'version',
    'version_info',
]
