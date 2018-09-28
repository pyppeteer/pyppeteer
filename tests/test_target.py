#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from syncer import sync

from .base import BaseTestCase


class TestTarget(BaseTestCase):
    @sync
    async def test_targets(self):
        targets = self.browser.targets()
        _list = [target for target in targets
                 if target.type == 'page' and target.url == 'about:blank']
        self.assertTrue(any(_list))
        target_types = [t.type for t in targets]
        self.assertIn('browser', target_types)

    @sync
    async def test_return_all_pages(self):
        pages = await self.context.pages()
        self.assertEqual(len(pages), 1)
        self.assertIn(self.page, pages)

    @sync
    async def test_browser_target(self):
        targets = self.browser.targets()
        browserTarget = [t for t in targets if t.type == 'browser']
        self.assertTrue(browserTarget)

    @sync
    async def test_default_page(self):
        pages = await self.browser.pages()
        page = [page for page in pages if page != self.page][0]
        self.assertEqual(await page.evaluate('["Hello", "world"].join(" ")'),
                         'Hello world')
        self.assertTrue(await page.J('body'))

    @sync
    async def test_report_new_page(self):
        otherPagePromise = asyncio.get_event_loop().create_future()
        self.context.once('targetcreated',
                          lambda target: otherPagePromise.set_result(target))
        await self.page.evaluate(
            'url => window.open(url)',
            'http://127.0.0.1:{}'.format(self.port))
        otherPage = await (await otherPagePromise).page()

        self.assertIn('127.0.0.1', otherPage.url)
        self.assertEqual(
            await otherPage.evaluate('["Hello", "world"].join(" ")'),
            'Hello world')
        self.assertTrue(await otherPage.J('body'))

        pages = await self.context.pages()
        self.assertIn(self.page, pages)
        self.assertIn(otherPage, pages)

        closePagePromise = asyncio.get_event_loop().create_future()

        async def get_close_page(target):
            page = await target.page()
            closePagePromise.set_result(page)

        self.context.once('targetdestroyed',
                          lambda t: asyncio.ensure_future(get_close_page(t)))
        await otherPage.close()
        self.assertEqual(await closePagePromise, otherPage)

        pages = await self.context.pages()
        self.assertIn(self.page, pages)
        self.assertNotIn(otherPage, pages)

    @sync
    async def test_report_service_worker(self):
        await self.page.goto(self.url + 'empty')
        createdTargetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetcreated',
                          lambda t: createdTargetPromise.set_result(t))

        await self.page.goto(self.url + 'static/serviceworkers/empty/sw.html')
        createdTarget = await createdTargetPromise
        self.assertEqual(createdTarget.type, 'service_worker')
        self.assertEqual(
            createdTarget.url, self.url + 'static/serviceworkers/empty/sw.js')

        destroyedTargetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetdestroyed',
                          lambda t: destroyedTargetPromise.set_result(t))
        await self.page.evaluate(
            '() => window.registrationPromise.then(reg => reg.unregister())')
        destroyedTarget = await destroyedTargetPromise
        self.assertEqual(destroyedTarget, createdTarget)

    @sync
    async def test_url_change(self):
        await self.page.goto(self.url + 'empty')

        changedTargetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetchanged',
                          lambda t: changedTargetPromise.set_result(t))
        await self.page.goto('http://127.0.0.1:{}/'.format(self.port))
        changedTarget = await changedTargetPromise
        self.assertEqual(changedTarget.url,
                         'http://127.0.0.1:{}/'.format(self.port))

        changedTargetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetchanged',
                          lambda t: changedTargetPromise.set_result(t))
        await self.page.goto(self.url + 'empty')
        changedTarget = await changedTargetPromise
        self.assertEqual(changedTarget.url, self.url + 'empty')

    @sync
    async def test_not_report_uninitialized_page(self):
        changedTargets = []

        def listener(target):
            changedTargets.append(target)

        self.context.on('targetchanged', listener)

        targetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetcreated',
                          lambda t: targetPromise.set_result(t))
        newPagePromise = asyncio.ensure_future(self.context.newPage())
        target = await targetPromise
        self.assertEqual(target.url, 'about:blank')

        newPage = await newPagePromise
        targetPromise2 = asyncio.get_event_loop().create_future()
        self.context.once('targetcreated',
                          lambda t: targetPromise2.set_result(t))
        evaluatePromise = asyncio.ensure_future(
            newPage.evaluate('window.open("about:blank")'))
        target2 = await targetPromise2
        self.assertEqual(target2.url, 'about:blank')
        await evaluatePromise
        await newPage.close()

        self.assertFalse(changedTargets)
        self.context.remove_listener('targetchanged', listener)

        # cleanup
        await (await target2.page()).close()

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_crash_while_redirect(self):
        pass

    @sync
    async def test_opener(self):
        await self.page.goto(self.url + 'empty')
        targetPromise = asyncio.get_event_loop().create_future()
        self.context.once('targetcreated',
                          lambda target: targetPromise.set_result(target))
        await self.page.goto(self.url + 'static/popup/window-open.html')
        createdTarget = await targetPromise
        self.assertEqual(
            (await createdTarget.page()).url,
            self.url + 'static/popup/popup.html',
        )
        self.assertEqual(createdTarget.opener, self.page.target)
        self.assertIsNone(self.page.target.opener)
        await (await createdTarget.page()).close()
