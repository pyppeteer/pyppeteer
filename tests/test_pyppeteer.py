#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import unittest

from syncer import sync

from pyppeteer.launcher import launch
from pyppeteer.util import install_asyncio, get_free_port
from server import get_application, BASE_HTML


def setUpModule():
    install_asyncio()


class TestPyppeteer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.browser = launch()
        cls.page = sync(cls.browser.newPage())

    @classmethod
    def tearDownModule(cls):
        cls.browser.close()
        cls.server.stop()

    def setUp(self):
        self.url = 'http://localhost:{}/'.format(self.port)
        sync(self.page.goto(self.url))

    @sync
    async def test_get(self):
        self.assertEqual(await self.page.title(), 'main')
        self.assertEqual(self.page.url, self.url)
        self.elm = await self.page.querySelector('h1#hello')
        self.assertTrue(self.elm)
        await self.page.goto('about:blank')
        self.assertEqual(self.page.url, 'about:blank')

    @sync
    async def test_plain_text(self):
        text = await self.page.plainText()
        self.assertEqual(text.split(), ['Hello', 'link1', 'link2'])

    @sync
    async def test_content(self):
        html = await self.page.content()
        self.assertEqual(html.replace('\n', ''), BASE_HTML.replace('\n', ''))

    @sync
    async def test_element(self):
        elm = await self.page.querySelector('h1')
        text = await elm.evaluate('(element) => element.textContent')
        self.assertEqual('Hello', text)

    @sync
    async def test_elements(self):
        elms = await self.page.querySelectorAll('a')
        self.assertEqual(len(elms), 2)
        elm1 = elms[0]
        elm2 = elms[1]
        self.assertEqual(await elm1.attribute('id'), 'link1')
        self.assertEqual(await elm2.attribute('id'), 'link2')

    @sync
    async def test_element_inner_html(self):
        elm = await self.page.querySelector('h1')
        text = await elm.evaluate('(element) => element.innerHTML')
        self.assertEqual('Hello', text)

    @sync
    async def test_element_outer_html(self):
        elm = await self.page.querySelector('h1')
        text = await elm.evaluate('(element) => element.outerHTML')
        self.assertEqual('<h1 id="hello">Hello</h1>', text)

    @sync
    async def test_element_attr(self):
        elm = await self.page.querySelector('h1')
        _id = await elm.attribute('id')
        self.assertEqual('hello', _id)

    @sync
    async def test_click(self):
        await self.page.click('#link1')
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')
        elm = await self.page.querySelector('h1#link1')
        self.assertTrue(elm)

    @sync
    async def test_wait_for_timeout(self):
        await self.page.click('#link1')
        await self.page.waitFor(0.1)
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_elm_click(self):
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.click()
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')

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
    async def test_cookies(self):
        cookies = await self.page.cookies()
        self.assertEqual(cookies, [])
        await self.page.evaluate(
            '() => {document.cookie = "username=John Doe"}'
        )
        cookies = await self.page.cookies()
        self.assertEqual(cookies, [{
            'name': 'username',
            'value': 'John Doe',
            'domain': 'localhost',
            'path': '/',
            'expires': 0,
            'size': 16,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])
        await self.page.setCookie({'name': 'password', 'value': '123456'})
        cookies = await self.page.evaluate(
            '() => document.cookie'
        )
        self.assertEqual(cookies, 'username=John Doe; password=123456')
        cookies = await self.page.cookies()
        self.assertEqual(cookies, [{
            'name': 'password',
            'value': '123456',
            'domain': 'localhost',
            'path': '/',
            'expires': 0,
            'size': 14,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }, {
            'name': 'username',
            'value': 'John Doe',
            'domain': 'localhost',
            'path': '/',
            'expires': 0,
            'size': 16,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])
        await self.page.deleteCookie({'name': 'username'})
        cookies = await self.page.evaluate(
            '() => document.cookie'
        )
        self.assertEqual(cookies, 'password=123456')
        cookies = await self.page.cookies()
        self.assertEqual(cookies, [{
            'name': 'password',
            'value': '123456',
            'domain': 'localhost',
            'path': '/',
            'expires': 0,
            'size': 14,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])

    @sync
    async def test_redirect(self):
        await self.page.goto(self.url + 'redirect1')
        await self.page.waitForSelector('h1#red2')
        self.assertEqual(await self.page.plainText(), 'redirect2')


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.url = 'http://localhost:{}/'.format(cls.port)
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.browser = launch(headless=True)

    def setUp(self):
        self.page = sync(self.browser.newPage())
        sync(self.page.goto(self.url))

    def tearDown(self):
        sync(self.page.goto('about:blank'))

    @classmethod
    def tearDownModule(cls):
        cls.browser.close()
        cls.server.stop()

    @sync
    async def test_alert(self):
        def dialog_test(dialog):
            self.assertEqual(dialog.type, 'alert')
            self.assertEqual(dialog.defaultValue(), '')
            self.assertEqual(dialog.message(), 'yo')
            asyncio.ensure_future(dialog.accept())
        self.page.on('dialog', dialog_test)
        await self.page.evaluate('() => alert("yo")')

    @sync
    async def test_prompt(self):
        def dialog_test(dialog):
            self.assertEqual(dialog.type, 'prompt')
            self.assertEqual(dialog.defaultValue(), 'yes.')
            self.assertEqual(dialog.message(), 'question?')
            asyncio.ensure_future(dialog.accept('answer!'))
        self.page.on('dialog', dialog_test)
        answer = await self.page.evaluate('() => prompt("question?", "yes.")')
        self.assertEqual(answer, 'answer!')

    @sync
    async def test_prompt_dismiss(self):
        def dismiss_test(dialog, *args):
            asyncio.ensure_future(dialog.dismiss())
        self.page.on('dialog', dismiss_test)
        result = await self.page.evaluate('() => prompt("question?", "yes.")')
        self.assertIsNone(result)
