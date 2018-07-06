#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import signal
from syncer import sync

from .base import BaseTestCase
from pyppeteer.errors import *


class TestBrowserCrash(BaseTestCase):
    @classmethod
    def tearDownClass(cls):
        pass

    def tearDown(self):
        pass

    @sync
    async def test_browser_crash_send(self):
        await self.page.goto(self.url)
        element = await self.page.querySelector("title")
        os.kill(self.browser.process.pid, signal.SIGKILL)
        with self.assertRaises(NetworkError):
            await self.page.querySelector("title")
        with self.assertRaises(NetworkError):
            await self.page.querySelector("title")
        with self.assertRaises(ConnectionError):
            await self.browser.newPage()
