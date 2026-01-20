#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from copy import deepcopy
import os
from pathlib import Path
import unittest

from syncer import sync

from pyppeteer import connect, launch

from .base import BaseTestCase, DEFAULT_OPTIONS
from .utils import waitEvent


class TestBrowser(unittest.TestCase):
    extensionPath = Path(__file__).parent / 'static' / 'simple-extension'
    extensionOptions = {
        'headless': False,
        'args': [
            '--no-sandbox',
            '--disable-extensions-except={}'.format(extensionPath),
            '--load-extensions={}'.format(extensionPath),
        ]
    }

    def waitForBackgroundPageTarget(self, browser):
        promise = asyncio.get_event_loop().create_future()
        for target in browser.targets():
            if target.type == 'background_page':
                promise.set_result(target)
                return promise

        def _listener(target) -> None:
            if target.type != 'background_page':
                return
            browser.removeListener(_listener)
            promise.set_result(target)

        browser.on('targetcreated', _listener)
        return promise

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

        await asyncio.wait([
            browser2.disconnect(),
            waitEvent(browser2, 'disconnected'),
        ])
        self.assertEqual(len(discon), 0)
        self.assertEqual(len(discon1), 0)
        self.assertEqual(len(discon2), 1)

        await asyncio.wait([
            waitEvent(browser1, 'disconnected'),
            waitEvent(browser, 'disconnected'),
            browser.close(),
        ])
        self.assertEqual(len(discon), 1)
        self.assertEqual(len(discon1), 1)
        self.assertEqual(len(discon2), 1)

    @sync
    async def test_crash(self):
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

    @unittest.skipIf('CI' in os.environ, 'skip in-browser test on CI server')
    @sync
    async def test_background_target_type(self):
        browser = await launch(self.extensionOptions)
        page = await browser.newPage()
        backgroundPageTarget = await self.waitForBackgroundPageTarget(browser)
        await page.close()
        await browser.close()
        self.assertTrue(backgroundPageTarget)

    @unittest.skipIf('CI' in os.environ, 'skip in-browser test on CI server')
    @sync
    async def test_OOPIF(self):
        options = deepcopy(DEFAULT_OPTIONS)
        options['headless'] = False
        browser = await launch(options)
        page = await browser.newPage()
        example_page = 'http://example.com/'
        await page.goto(example_page)
        await page.setRequestInterception(True)

        async def intercept(req):
            await req.respond({'body': 'YO, GOOGLE.COM'})

        page.on('request', lambda req: asyncio.ensure_future(intercept(req)))
        await page.evaluate('''() => {
            const frame = document.createElement('iframe');
            frame.setAttribute('src', 'https://google.com/');
            document.body.appendChild(frame);
            return new Promise(x => frame.onload = x);
        }''')
        await page.waitForSelector('iframe[src="https://google.com/"]')
        urls = []
        for frame in page.frames:
            urls.append(frame.url)
        urls.sort()
        self.assertEqual(urls, [example_page, 'https://google.com/'])
        await browser.close()

    @unittest.skipIf('CI' in os.environ, 'skip in-browser test on CI server')
    @sync
    async def test_background_page(self):
        browserWithExtension = await launch(self.extensionOptions)
        backgroundPageTarget = await self.waitForBackgroundPageTarget(browserWithExtension)  # noqa: E501
        self.assertIsNotNone(backgroundPageTarget)
        page = await backgroundPageTarget.page()
        self.assertEqual(await page.evaluate('2 * 3'), 6)
        await browserWithExtension.close()


class TestPageClose(BaseTestCase):
    @sync
    async def test_not_visible_in_browser_pages(self):
        newPage = await self.context.newPage()
        self.assertIn(newPage, await self.browser.pages())
        await newPage.close()
        self.assertNotIn(newPage, await self.browser.pages())

    @sync
    async def test_before_unload(self):
        newPage = await self.context.newPage()
        await newPage.goto(self.url + 'static/beforeunload.html')
        await newPage.click('body')
        asyncio.ensure_future(newPage.close(runBeforeUnload=True))
        dialog = await waitEvent(newPage, 'dialog')
        self.assertEqual(dialog.type, 'beforeunload')
        self.assertEqual(dialog.defaultValue, '')
        self.assertEqual(dialog.message, '')
        asyncio.ensure_future(dialog.accept())
        await waitEvent(newPage, 'close')

    @sync
    async def test_page_close_state(self):
        newPage = await self.context.newPage()
        self.assertFalse(newPage.isClosed())
        await newPage.close()
        self.assertTrue(newPage.isClosed())
