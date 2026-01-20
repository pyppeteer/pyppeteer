#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from pyppeteer import connect
from pyppeteer.errors import BrowserError

from syncer import sync

from .base import BaseTestCase
from .utils import waitEvent


class BrowserBaseTestCase(BaseTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


class TestBrowserContext(BrowserBaseTestCase):
    @sync
    async def test_default_context(self):
        self.assertEqual(len(self.browser.browserContexts), 1)
        defaultContext = self.browser.browserContexts[0]
        self.assertFalse(defaultContext.isIncognito())
        with self.assertRaises(BrowserError) as cm:
            await defaultContext.close()
        self.assertIn('cannot be closed', cm.exception.args[0])

    @unittest.skip('this test not pass in some environment')
    @sync
    async def test_incognito_context(self):
        self.assertEqual(len(self.browser.browserContexts), 1)
        context = await self.browser.createIncognitoBrowserContext()
        self.assertTrue(context.isIncognito())
        self.assertEqual(len(self.browser.browserContexts), 2)
        self.assertIn(context, self.browser.browserContexts)
        await context.close()
        self.assertEqual(len(self.browser.browserContexts), 1)

    @sync
    async def test_close_all_targets_once(self):
        self.assertEqual(len(await self.browser.pages()), 1)
        context = await self.browser.createIncognitoBrowserContext()
        await context.newPage()
        self.assertEqual(len(await self.browser.pages()), 2)
        self.assertEqual(len(await context.pages()), 1)
        await context.close()
        self.assertEqual(len(await self.browser.pages()), 1)

    @sync
    async def test_window_open_use_parent_tab_context(self):
        context = await self.browser.createIncognitoBrowserContext()
        page = await context.newPage()
        await page.goto(self.url + 'empty')
        asyncio.ensure_future(
            page.evaluate('url => window.open(url)', self.url + 'empty'))
        popupTarget = await waitEvent(self.browser, 'targetcreated')
        self.assertEqual(popupTarget.browserContext, context)
        await context.close()

    @sync
    async def test_fire_target_event(self):
        context = await self.browser.createIncognitoBrowserContext()
        events = []
        context.on('targetcreated', lambda t: events.append('CREATED: ' + t.url))  # noqa: E501
        context.on('targetchanged', lambda t: events.append('CHANGED: ' + t.url))  # noqa: E501
        context.on('targetdestroyed', lambda t: events.append('DESTROYED: ' + t.url))  # noqa: E501
        page = await context.newPage()
        await page.goto(self.url + 'empty')
        await page.close()
        self.assertEqual(events, [
            'CREATED: about:blank',
            'CHANGED: ' + self.url + 'empty',
            'DESTROYED: ' + self.url + 'empty',
        ])

    @unittest.skip('this test not pass in some environment')
    @sync
    async def test_isolate_local_storage_and_cookie(self):
        context1 = await self.browser.createIncognitoBrowserContext()
        context2 = await self.browser.createIncognitoBrowserContext()
        self.assertEqual(len(context1.targets()), 0)
        self.assertEqual(len(context2.targets()), 0)

        # create a page in the first incognito context
        page1 = await context1.newPage()
        await page1.goto(self.url + 'empty')
        await page1.evaluate('''() => {
            localStorage.setItem('name', 'page1');
            document.cookie = 'name=page1';
        }''')

        self.assertEqual(len(context1.targets()), 1)
        self.assertEqual(len(context2.targets()), 0)

        # create a page in the second incognito context
        page2 = await context2.newPage()
        await page2.goto(self.url + 'empty')
        await page2.evaluate('''() => {
            localStorage.setItem('name', 'page2');
            document.cookie = 'name=page2';
        }''')

        self.assertEqual(len(context1.targets()), 1)
        self.assertEqual(context1.targets()[0], page1.target)
        self.assertEqual(len(context2.targets()), 1)
        self.assertEqual(context2.targets()[0], page2.target)

        # make sure pages don't share local storage and cookie
        self.assertEqual(await page1.evaluate('localStorage.getItem("name")'), 'page1')  # noqa: E501
        self.assertEqual(await page1.evaluate('document.cookie'), 'name=page1')
        self.assertEqual(await page2.evaluate('localStorage.getItem("name")'), 'page2')  # noqa: E501
        self.assertEqual(await page2.evaluate('document.cookie'), 'name=page2')

        await context1.close()
        await context2.close()
        self.assertEqual(len(self.browser.browserContexts), 1)

    @sync
    async def test_across_session(self):
        self.assertEqual(len(self.browser.browserContexts), 1)
        context = await self.browser.createIncognitoBrowserContext()
        self.assertEqual(len(self.browser.browserContexts), 2)
        remoteBrowser = await connect(
            browserWSEndpoint=self.browser.wsEndpoint)
        contexts = remoteBrowser.browserContexts
        self.assertEqual(len(contexts), 2)
        await remoteBrowser.disconnect()
        await context.close()
