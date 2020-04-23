#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import unittest

import pytest
from pyppeteer import launch
from pyppeteer.errors import NetworkError
from syncer import sync


class TestBrowserCrash(unittest.TestCase):
    @sync
    async def test_browser_crash_send(self):
        browser = await launch(args=['--no-sandbox'])
        page = await browser.newPage()
        await page.goto('about:blank')
        await page.querySelector("title")
        browser.process.terminate()
        browser.process.wait()

        if current_platform().startswith('win'):
            # wait for terminating browser process
            await asyncio.sleep(1)

        with pytest.raises(NetworkError):
            await page.querySelector("title")
        with pytest.raises(NetworkError):
            with self.assertLogs('pyppeteer', logging.ERROR):
                await page.querySelector("title")
        with pytest.raises(ConnectionError):
            await browser.newPage()
