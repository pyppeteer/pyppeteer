#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from pyppeteer import connect
from pyppeteer.errors import BrowserError

from syncer import sync

from .base import BaseTestCase
from .utils import waitEvent
import pytest


class BrowserBaseTestCase(BaseTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


class TestBrowserContext(BrowserBaseTestCase):
    @sync
    async def test_default_context(self):
        assert len(self.browser.browserContexts) == 1
        defaultContext = self.browser.browserContexts[0]
        assert not defaultContext.isIncognito()
        with pytest.raises(BrowserError) as cm:
            await defaultContext.close()
        assert 'cannot be closed' in cm.exception.args[0]

    @unittest.skip('this test not pass in some environment')
    @sync
    async def test_incognito_context(self):
        assert len(self.browser.browserContexts) == 1
        context = await self.browser.createIncognitoBrowserContext()
        assert context.isIncognito()
        assert len(self.browser.browserContexts) == 2
        assert context in self.browser.browserContexts
        await context.close()
        assert len(self.browser.browserContexts) == 1

    @sync
    async def test_close_all_targets_once(self):
        assert len(await self.browser.pages()) == 1
        context = await self.browser.createIncognitoBrowserContext()
        await context.newPage()
        assert len(await self.browser.pages()) == 2
        assert len(await context.pages()) == 1
        await context.close()
        assert len(await self.browser.pages()) == 1

    @sync
    async def test_window_open_use_parent_tab_context(self):
        context = await self.browser.createIncognitoBrowserContext()
        page = await context.newPage()
        await page.goto(self.url + 'empty')
        asyncio.ensure_future(
            page.evaluate('url => window.open(url)', self.url + 'empty'))
        popupTarget = await waitEvent(self.browser, 'targetcreated')
        assert popupTarget.browserContext == context
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
        assert events == [
            'CREATED: about:blank',
            'CHANGED: ' + self.url + 'empty',
            'DESTROYED: ' + self.url + 'empty',
        ]

    @unittest.skip('this test not pass in some environment')
    @sync
    async def test_isolate_local_storage_and_cookie(self):
        context1 = await self.browser.createIncognitoBrowserContext()
        context2 = await self.browser.createIncognitoBrowserContext()
        assert len(context1.targets()) == 0
        assert len(context2.targets()) == 0

        # create a page in the first incognito context
        page1 = await context1.newPage()
        await page1.goto(self.url + 'empty')
        await page1.evaluate('''() => {
            localStorage.setItem('name', 'page1');
            document.cookie = 'name=page1';
        }''')

        assert len(context1.targets()) == 1
        assert len(context2.targets()) == 0

        # create a page in the second incognito context
        page2 = await context2.newPage()
        await page2.goto(self.url + 'empty')
        await page2.evaluate('''() => {
            localStorage.setItem('name', 'page2');
            document.cookie = 'name=page2';
        }''')

        assert len(context1.targets()) == 1
        assert context1.targets()[0] == page1.target
        assert len(context2.targets()) == 1
        assert context2.targets()[0] == page2.target

        # make sure pages don't share local storage and cookie
        assert await page1.evaluate('localStorage.getItem("name")') == 'page1'  # noqa: E501
        assert await page1.evaluate('document.cookie') == 'name=page1'
        assert await page2.evaluate('localStorage.getItem("name")') == 'page2'  # noqa: E501
        assert await page2.evaluate('document.cookie') == 'name=page2'

        await context1.close()
        await context2.close()
        assert len(self.browser.browserContexts) == 1

    @sync
    async def test_across_session(self):
        assert len(self.browser.browserContexts) == 1
        context = await self.browser.createIncognitoBrowserContext()
        assert len(self.browser.browserContexts) == 2
        remoteBrowser = await connect(
            browserWSEndpoint=self.browser.wsEndpoint)
        contexts = remoteBrowser.browserContexts
        assert len(contexts) == 2
        await remoteBrowser.disconnect()
        await context.close()
