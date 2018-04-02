#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.launcher import connect

from base import BaseTestCase, DEFAULT_OPTIONS


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


class TestTarget(BaseTestCase):
    @sync
    async def test_targets(self):
        targets = self.browser.targets()
        _list = [target for target in targets
                 if target.type == 'page' and target.url == 'about:blank']
        self.assertTrue(any(_list))
        _list = [target for target in targets
                 if target.type == 'other' and target.url == '']
        self.assertTrue(any(_list))

    @sync
    async def test_return_all_pages(self):
        pages = await self.browser.pages()
        self.assertEqual(len(pages), 2)
        self.assertIn(self.page, pages)
        self.assertNotEqual(pages[0], pages[1])

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
        self.browser.once('targetcreated',
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

        pages = await self.browser.pages()
        self.assertIn(self.page, pages)
        self.assertIn(otherPage, pages)

        closePagePromise = asyncio.get_event_loop().create_future()

        async def get_close_page(target):
            page = await target.page()
            closePagePromise.set_result(page)

        self.browser.once('targetdestroyed',
                          lambda t: asyncio.ensure_future(get_close_page(t)))
        await otherPage.close()
        self.assertEqual(await closePagePromise, otherPage)

        pages = await self.browser.pages()
        self.assertIn(self.page, pages)
        self.assertNotIn(otherPage, pages)

    @sync
    async def test_report_service_worker(self):
        await self.page.goto(self.url + 'empty')
        createdTargetPromise = asyncio.get_event_loop().create_future()
        self.browser.once('targetcreated',
                          lambda t: createdTargetPromise.set_result(t))

        registration = await self.page.evaluateHandle(
            '() => navigator.serviceWorker.register("static/sw.js")')
        createdTarget = await createdTargetPromise
        self.assertEqual(createdTarget.type, 'service_worker')
        self.assertEqual(createdTarget.url, self.url + 'static/sw.js')

        destroyedTargetPromise = asyncio.get_event_loop().create_future()
        self.browser.once('targetdestroyed',
                          lambda t: destroyedTargetPromise.set_result(t))
        await self.page.evaluate('(reg) => reg.unregister()', registration)
        destroyedTarget = await destroyedTargetPromise
        self.assertEqual(destroyedTarget, createdTarget)

    @sync
    async def test_url_change(self):
        await self.page.goto(self.url + 'empty')

        changedTargetPromise = asyncio.get_event_loop().create_future()
        self.browser.once('targetchanged',
                          lambda t: changedTargetPromise.set_result(t))
        await self.page.goto('http://127.0.0.1:{}/'.format(self.port))
        changedTarget = await changedTargetPromise
        self.assertEqual(changedTarget.url,
                         'http://127.0.0.1:{}/'.format(self.port))

        changedTargetPromise = asyncio.get_event_loop().create_future()
        self.browser.once('targetchanged',
                          lambda t: changedTargetPromise.set_result(t))
        await self.page.goto(self.url + 'empty')
        changedTarget = await changedTargetPromise
        self.assertEqual(changedTarget.url, self.url + 'empty')

    @sync
    async def test_not_report_uninitialized_page(self):
        changedTargets = []

        def listener(target):
            changedTargets.append(target)

        self.browser.on('targetchanged', listener)

        targetPromise = asyncio.get_event_loop().create_future()
        self.browser.once('targetcreated',
                          lambda t: targetPromise.set_result(t))
        newPagePromise = asyncio.ensure_future(self.browser.newPage())
        target = await targetPromise
        self.assertEqual(target.url, 'about:blank')

        newPage = await newPagePromise
        targetPromise2 = asyncio.get_event_loop().create_future()
        self.browser.once('targetcreated',
                          lambda t: targetPromise2.set_result(t))
        evaluatePromise = asyncio.ensure_future(
            newPage.evaluate('window.open("about:blank")'))
        target2 = await targetPromise2
        self.assertEqual(target2.url, 'about:blank')
        await evaluatePromise
        await newPage.close()

        self.assertFalse(changedTargets)
        self.browser.remove_listener('targetchanged', listener)

        # cleanup
        await (await target2.page()).close()

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_crash_while_redirect(self):
        pass
