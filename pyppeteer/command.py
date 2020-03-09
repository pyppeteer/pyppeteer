#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Commands for Pyppeteer."""
from pprint import pprint

from pyppeteer.browser_fetcher import BrowserFetcher


def install() -> None:
    """Download chromium if not install."""
    dl = BrowserFetcher()
    pprint(dl.download())
