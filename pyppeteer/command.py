#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Commands for Pyppeteer."""
import argparse

from pyppeteer.browser_fetcher import BrowserFetcher


def install() -> None:
    """Download and Chromium/Firefox to specified folder"""
    parser = argparse.ArgumentParser(description=install.__doc__)
    parser.add_argument('-r', '--revision', action="store", type=str, default=None)
    parser.add_argument('-p', '--product', action="store", type=str, default=None)
    parser.add_argument('-l', '--location', action="store")
    parsed = parser.parse_args()
    dl = BrowserFetcher(parsed.location)
    dl.download(parsed.revision)


if __name__ == '__main__':
    install()
