#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from syncer import sync

from pyppeteer import Pyppeteer
from pyppeteer.browser import Browser
from pyppeteer.util import get_free_port

from .server import get_application

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}

browser: Browser = sync(Pyppeteer().launch(args='--no-sandbox'))