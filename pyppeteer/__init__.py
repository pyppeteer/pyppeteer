#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta data for pyppeteer."""

import logging

__author__ = """Hiroyuki Takagi"""
__email__ = 'miyako.dev@gmail.com'
__version__ = '0.0.17'
__chromimum_revision__ = '543305'
__base_puppeteer_version__ = 'v1.0.0'

# Setup root logger
_logger = logging.getLogger('pyppeteer')
_log_handler = logging.StreamHandler()
_fmt = '[{levelname[0]}:{name}] {msg}'
_formatter = logging.Formatter(fmt=_fmt, style='{')
_log_handler.setFormatter(_formatter)
_log_handler.setLevel(logging.DEBUG)
_logger.addHandler(_log_handler)
_logger.propagate = False
# logger.setLevel(logging.DEBUG)

from pyppeteer.launcher import launch, executablePath  # noqa: E402
from pyppeteer.launcher import defaultArgs  # noqa: E402

version = __version__
version_info = tuple(int(i) for i in version.split('.'))

__all__ = [
    'launch',
    'executablePath',
    'defaultArgs',
    'version',
    'version_info',
]
