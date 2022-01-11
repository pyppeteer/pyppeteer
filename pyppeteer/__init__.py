#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta data for pyppeteer."""

import logging
import os

from appdirs import AppDirs

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
    __version__ = None


__chromium_revision__ = '588429'
__base_puppeteer_version__ = 'v1.6.0'
__pyppeteer_home__ = os.environ.get('PYPPETEER_HOME', AppDirs('pyppeteer').user_data_dir)  # type: str
DEBUG = False

from pyppeteer.launcher import connect, executablePath, launch, defaultArgs  # noqa: E402; noqa: E402

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
