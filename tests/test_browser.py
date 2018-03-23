#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.launcher import connect

from base import DEFAULT_OPTIONS


class TestBrowser(unittest.TestCase):
    @sync
    async def test_browser_process(self):
        browser = await launch(DEFAULT_OPTIONS)
        process = browser.process
        self.assertGreater(process.pid, 0)
        wsEndpoint = browser.wsEndpoint
        browser2 = await connect({'browserWSEndpoint': wsEndpoint})
        self.assertIsNone(browser2.process)
        await browser.close()

    @sync
    async def test_version(self):
        browser = await launch(DEFAULT_OPTIONS)
        version = await browser.version()
        self.assertTrue(len(version) > 0)
        self.assertTrue(version.startswith('Headless'))
        await browser.close()

    @sync
    async def test_user_agent(self):
        browser = await launch(DEFAULT_OPTIONS)
        userAgent = await browser.userAgent()
        self.assertGreater(len(userAgent), 0)
        self.assertIn('WebKit', userAgent)
        await browser.close()

    @unittest.skip('Could not pass this test')
    @sync
    async def test_disconnect(self):
        browser = await launch(DEFAULT_OPTIONS)
        endpoint = browser.wsEndpoint
        browser1 = await connect(browserWSEndpoint=endpoint)
        browser2 = await connect(browserWSEndpoint=endpoint)
        discon = []
        discon1 = []
        discon2 = []
        browser.on('disconnected', lambda: discon.append(1))
        browser1.on('disconnected', lambda: discon1.append(1))
        browser2.on('disconnected', lambda: discon2.append(1))

        await browser2.disconnect()
        self.assertEqual(len(discon), 0)
        self.assertEqual(len(discon1), 0)
        self.assertEqual(len(discon2), 1)

        await browser.close()
        self.assertEqual(len(discon), 1)
        self.assertEqual(len(discon1), 1)
        self.assertEqual(len(discon2), 1)

    @sync
    async def test_crash(self) -> None:
        browser = await launch(DEFAULT_OPTIONS)
        page = await browser.newPage()
        errors = []
        page.on('error', lambda e: errors.append(e))
        asyncio.ensure_future(page.goto('chrome://crash'))
        for i in range(100):
            await asyncio.sleep(0.01)
            if errors:
                break
        await browser.close()
        self.assertTrue(errors)
