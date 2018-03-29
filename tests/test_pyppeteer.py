#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import logging
from pathlib import Path
import time
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.errors import ElementHandleError, PageError
from pyppeteer.util import get_free_port

from base import BaseTestCase, DEFAULT_OPTIONS
from server import get_application, BASE_HTML


class TestPyppeteer(BaseTestCase):
    @sync
    async def test_get(self):
        self.assertEqual(await self.page.title(), 'main')
        self.assertEqual(self.page.url, self.url)
        self.elm = await self.page.querySelector('h1#hello')
        self.assertTrue(self.elm)
        await self.page.goto('about:blank')
        self.assertEqual(self.page.url, 'about:blank')

    @sync
    async def test_get_https(self):
        await self.page.goto('https://example.com/')
        self.assertEqual(self.page.url, 'https://example.com/')

    @sync
    async def test_get_facebook(self):
        await self.page.goto('https://www.facebook.com/')
        self.assertEqual(self.page.url, 'https://www.facebook.com/')

    @sync
    async def test_plain_text_depr(self):
        with self.assertLogs('pyppeteer', logging.WARN) as log:
            text = await self.page.plainText()
            self.assertIn('deprecated', log.records[0].msg)
        self.assertEqual(text.split(), ['Hello', 'link1', 'link2'])

    @sync
    async def test_content(self):
        html = await self.page.content()
        self.assertEqual(html.replace('\n', ''), BASE_HTML.replace('\n', ''))

    @sync
    async def test_hover(self):
        await self.page.hover('a#link1')
        _id = await self.page.evaluate('document.querySelector("a:hover").id')
        self.assertEqual(_id, 'link1')

        await self.page.hover('a#link2')
        _id = await self.page.evaluate('document.querySelector("a:hover").id')
        self.assertEqual(_id, 'link2')

    @sync
    async def test_hover_not_found(self):
        with self.assertRaises(PageError):
            await self.page.hover('#no-such-element')
        elm = await self.page.J('h1')
        await self.page.evaluate(
            'document.querySelector("h1").remove();'
        )
        with self.assertRaises(ElementHandleError):
            await elm.hover()

    @sync
    async def test_focus_not_found(self):
        with self.assertRaises(PageError):
            await self.page.focus('#no-such-element')

    @sync
    async def test_click(self):
        await self.page.click('#link1')
        await asyncio.sleep(0.05)
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')
        elm = await self.page.querySelector('h1#link1')
        self.assertTrue(elm)

    @sync
    async def test_tap(self):
        await self.page.tap('#link1')
        await asyncio.sleep(0.05)
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(self.page.url, self.url + '1')
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_wait_for_timeout(self):
        await self.page.click('#link1')
        await self.page.waitFor(0.1)
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_wait_for_function(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate(
            '() => {'
            '  setTimeout(() => {'
            '    document.body.innerHTML = "<section>a</section>"'
            '  }, 200)'
            '}'
        )
        await self.page.waitForFunction(
            '() => !!document.querySelector("section")'
        )
        self.assertIsNotNone(await self.page.querySelector('section'))

    @sync
    async def test_wait_for_selector(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate(
            '() => {'
            '  setTimeout(() => {'
            '    document.body.innerHTML = "<section>a</section>"'
            '  }, 200)'
            '}'
        )
        await self.page.waitForSelector('section')
        self.assertIsNotNone(await self.page.querySelector('section'))

    @sync
    async def test_elm_click(self):
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.click()
        await asyncio.sleep(0.05)
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_elm_click_detached(self):
        btn1 = await self.page.querySelector('#link1')
        await self.page.evaluate(
            'document.querySelector("#link1").remove();'
        )
        with self.assertRaises(ElementHandleError):
            await btn1.click()

    @sync
    async def test_elm_tap(self):
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.tap()
        await asyncio.sleep(0.05)
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_elm_tap_detached(self):
        btn1 = await self.page.querySelector('#link1')
        await self.page.evaluate(
            'document.querySelector("#link1").remove();'
        )
        with self.assertRaises(ElementHandleError):
            await btn1.tap()

    @sync
    async def test_back_forward(self):
        await self.page.click('#link1')
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')
        await self.page.goBack()
        await self.page.waitForSelector('h1#hello')
        self.assertEqual(await self.page.title(), 'main')
        elm = await self.page.querySelector('h1#hello')
        self.assertTrue(elm)
        await self.page.goForward()
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')
        btn2 = await self.page.querySelector('#link1')
        self.assertTrue(btn2)

    @sync
    async def test_redirect(self):
        await self.page.goto(self.url + 'redirect1')
        await self.page.waitForSelector('h1#red2')
        text = await self.page.evaluate('() => document.body.innerText')
        self.assertEqual(text, 'redirect2')

    @sync
    async def test_all_pages(self):
        pages = await self.browser.pages()
        self.assertEqual(len(pages), 2)
        self.assertIn(self.page, pages)
        self.assertNotEqual(pages[0], pages[1])

    @sync
    async def test_original_page(self):
        pages = await self.browser.pages()
        originalPage = None
        for page in pages:
            if page != self.page:
                originalPage = page
                break
        self.assertEqual(await originalPage.evaluate('() => 1 + 2'), 3)
        self.assertTrue(await originalPage.J('body'))


class TestPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.url = 'http://localhost:{}/'.format(cls.port)
        cls.app = get_application()
        time.sleep(0.1)
        cls.server = cls.app.listen(cls.port)
        cls.browser = sync(launch(DEFAULT_OPTIONS))

    def setUp(self):
        self.page = sync(self.browser.newPage())
        sync(self.page.goto(self.url))

    def tearDown(self):
        sync(self.page.goto('about:blank'))

    @classmethod
    def tearDownClass(cls):
        sync(cls.browser.close())
        cls.server.stop()

    @sync
    async def test_close_page(self):
        await self.page.close()
        self.page = await self.browser.newPage()

    @sync
    async def test_viewport(self):
        await self.page.setViewport(dict(
            width=480,
            height=640,
            deviceScaleFactor=3,
            isMobile=True,
            hasTouch=True,
            isLandscape=True,
        ))

    @sync
    async def test_emulate(self):
        await self.page.emulate(dict(
            userAgent='test',
            viewport=dict(
                width=480,
                height=640,
                deviceScaleFactor=3,
                isMobile=True,
                hasTouch=True,
                isLandscape=True,
            ),
        ))

    @sync
    async def test_inject_file(self):  # deprecated
        tmp_file = Path('tmp.js')
        with tmp_file.open('w') as f:
            f.write('''
() => document.body.appendChild(document.createElement("section"))
            '''.strip())
        with self.assertLogs('pyppeteer', logging.WARN) as log:
            await self.page.injectFile(str(tmp_file))
            self.assertIn('deprecated', log.records[0].msg)
        await self.page.waitForSelector('section')
        self.assertIsNotNone(await self.page.J('section'))
        tmp_file.unlink()


class TestScreenshot(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.target_path = Path(__file__).resolve().parent / 'test.png'
        if self.target_path.exists():
            self.target_path.unlink()

    def tearDown(self):
        if self.target_path.exists():
            self.target_path.unlink()
        super().tearDown()

    @sync
    async def test_screenshot_large(self):
        page = await self.browser.newPage()
        await page.setViewport({
            'width': 2000,
            'height': 2000,
        })
        await page.goto(self.url + 'static/huge-page.html')
        options = {'path': str(self.target_path)}
        self.assertFalse(self.target_path.exists())
        await asyncio.wait_for(page.screenshot(options), 30)
        self.assertTrue(self.target_path.exists())
        with self.target_path.open('rb') as fh:
            bytes = fh.read()
            self.assertGreater(len(bytes), 2**20)
