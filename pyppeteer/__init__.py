#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta data for pyppeteer."""

import logging
import os

try:
    # noinspection PyCompatibility
    from importlib.metadata import version
except ModuleNotFoundError:
    # noinspection PyUnresolvedReferences
    # <3.8 backport
    from importlib_metadata import version

try:
    __version__ = version(__name__)
except Exception:
    pass

from appdirs import AppDirs

__chromium_revision__ = '588429'
__base_puppeteer_version__ = 'v1.6.0'
__pyppeteer_home__ = os.environ.get(
    'PYPPETEER_HOME', AppDirs('pyppeteer').user_data_dir)  # type: str
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

from pyppeteer.launcher import connect, launch, executablePath  # noqa: E402
from pyppeteer.launcher import defaultArgs  # noqa: E402

version = __version__
version_info = tuple(int(i) for i in version.split('.'))

__all__ = [
    'connect',
    'launch',
    'executablePath',
    'defaultArgs',
    'version',
    'version_info',
]
