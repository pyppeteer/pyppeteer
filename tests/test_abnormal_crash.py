#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.errors import NetworkError


class TestBrowserCrash(unittest.TestCase):
    @sync
    async def test_browser_crash_send(self):
        browser = await launch(args=['--no-sandbox'])
        page = await browser.newPage()
        await page.goto('about:blank')
        await page.querySelector("title")
        browser.process.terminate()
        browser.process.wait()
        with self.assertRaises(NetworkError):
            await page.querySelector("title")
        with self.assertRaises(NetworkError):
            with self.assertLogs('pyppeteer', logging.ERROR):
                await page.querySelector("title")
        with self.assertRaises(ConnectionError):
            await browser.newPage()
