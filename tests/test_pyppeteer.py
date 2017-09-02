#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
from pathlib import Path
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
    async def test_get_https(self):
        await self.page.goto('https://example.com/')
        self.assertEqual(self.page.url, 'https://example.com/')

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
        with self.assertLogs('pyppeteer', level='WARN') as cm:
            self.assertEqual(await elm1.attribute('id'), 'link1')
        self.assertIn('[DEPRECATED]', cm.output[0])
        with self.assertLogs('pyppeteer', level='WARN') as cm:
            self.assertEqual(await elm2.attribute('id'), 'link2')
        self.assertIn('[DEPRECATED]', cm.output[0])

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
        _id = await self.page.querySelectorEval('h1', ('(elm) => elm.id'))
        self.assertEqual('hello', _id)

    @sync
    async def test_click(self):
        await self.page.click('#link1')
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')
        elm = await self.page.querySelector('h1#link1')
        self.assertTrue(elm)

    @sync
    async def test_tap(self):
        await self.page.tap('#link1')
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
        await self.page.waitForSelector('h1#link1')
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_elm_tap(self):
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.tap()
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


class TestPage(unittest.TestCase):
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

    @sync
    async def test_user_agent(self):
        self.assertIn('Mozilla', await self.page.evaluate(
            '() => navigator.userAgent'))
        await self.page.setUserAgent('foobar')
        await self.page.goto(self.url)
        self.assertEqual('foobar', await self.page.evaluate(
            '() => navigator.userAgent'))

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
    async def test_inject_file(self):
        tmp_file = Path('tmp.js')
        with tmp_file.open('w') as f:
            f.write('''
() => document.body.appendChild(document.createElement("section"))
            '''.strip())
        await self.page.injectFile(str(tmp_file))
        await self.page.waitForSelector('section')
        self.assertIsNotNone(await self.page.J('section'))
        tmp_file.unlink()

    @sync
    async def test_tracing(self):
        outfile = Path(__file__).parent / 'trace.json'
        if outfile.is_file():
            outfile.unlink()
        await self.page.tracing.start({
            'path': str(outfile)
        })
        await self.page.goto(self.url)
        await self.page.tracing.stop()
        self.assertTrue(outfile.is_file())

    @sync
    async def test_interception_enable(self):
        await self.page.setRequestInterceptionEnabled(True)
        # await self.page.goto(self.url)

    @sync
    async def test_no_await_check_just_call(self):
        await self.page.setExtraHTTPHeaders({'a': 'b'})
        await self.page.addScriptTag('https://code.jquery.com/jquery-3.2.1.slim.min.js')  # noqa: E501
        await self.page.setContent('')
        await self.page.reload()
        await self.page.setJavaScriptEnabled(True)
        await self.page.emulateMedia()
        await self.page.evaluateOnNewDocument('() => 1 + 2')
