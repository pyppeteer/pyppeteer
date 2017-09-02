#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Meta data for pyppeteer."""

import logging

__author__ = """Hiroyuki Takagi"""
__email__ = 'miyako.dev@gmail.com'
__version__ = '0.0.6'
__chromimum_revision__ = '496140'

# Setup root logger
logger = logging.getLogger('pyppeteer')
_log_handler = logging.StreamHandler()
# fmt = '%(color)s[%(levelname)1.1s:%(name)s]%(end_color)s '
fmt = '[{levelname[0]}:{name}] {msg}'
formatter = logging.Formatter(fmt=fmt, style='{')
_log_handler.setFormatter(formatter)
_log_handler.setLevel(logging.DEBUG)
logger.addHandler(_log_handler)
logger.propagate = False
# logger.setLevel(logging.DEBUG)
