#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import math
from pathlib import Path
import sys
import time
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.errors import ElementHandleError, NetworkError, PageError
from pyppeteer.errors import TimeoutError, PyppeteerError
from pyppeteer.launcher import connect
from pyppeteer.util import get_free_port
from server import get_application, BASE_HTML

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}


class TestLauncher(unittest.TestCase):
    @sync
    async def test_launch(self):
        browser = await launch(DEFAULT_OPTIONS)
        await browser.newPage()
        await browser.close()

    @unittest.skip('should fix ignoreHTTPSErrors.')
    @sync
    async def test_ignore_https_errors(self):
        browser = await launch(DEFAULT_OPTIONS, ignoreHTTPSErrors=True)
        page = await browser.newPage()
        port = get_free_port()
        time.sleep(0.1)
        app = get_application()
        server = app.listen(port)
        response = await page.goto('https://localhost:{}'.format(port))
        self.assertTrue(response.ok)
        await browser.close()
        server.stop()

    @sync
    async def test_await_after_close(self):
        browser = await launch(DEFAULT_OPTIONS)
        page = await browser.newPage()
        promise = page.evaluate('() => new Promise(r => {})')
        await browser.close()
        with self.assertRaises(NetworkError):
            await promise

    @sync
    async def test_invalid_executable_path(self):
        with self.assertRaises(FileNotFoundError):
            await launch(DEFAULT_OPTIONS, executablePath='not-a-path')

    @sync
    async def test_connect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browser2 = await connect(browserWSEndpoint=browser.wsEndpoint)
        page = await browser2.newPage()
        self.assertEqual(await page.evaluate('() => 7 * 8'), 56)

        await browser2.disconnect()
        page2 = await browser.newPage()
        self.assertEqual(await page2.evaluate('() => 7 * 6'), 42)
        await browser.close()

    @sync
    async def test_reconnect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browserWSEndpoint = browser.wsEndpoint
        await browser.disconnect()

        browser2 = await connect(browserWSEndpoint=browserWSEndpoint)
        page = await browser2.newPage()
        self.assertEqual(await page.evaluate('() => 7 * 8'), 56)
        await browser.close()

    @sync
    async def test_version(self):
        browser = await launch(DEFAULT_OPTIONS)
        version = await browser.version()
        self.assertTrue(len(version) > 0)
        self.assertTrue(version.startswith('Headless'))


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        time.sleep(0.1)
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.browser = sync(launch(DEFAULT_OPTIONS))
        cls.page = sync(cls.browser.newPage())

    @classmethod
    def tearDownClass(cls):
        sync(cls.browser.close())
        cls.server.stop()

    def setUp(self):
        self.url = 'http://localhost:{}/'.format(self.port)
        sync(self.page.goto(self.url))

    def tearDown(self):
        sync(self.page.goto('about:blank'))


class TestPyppeteer(BaseTestCase):
    @sync
    async def test_get_http(self):
        response = await self.page.goto('http://example.com/')
        self.assertEqual(response.status, 200)
        self.assertEqual(self.page.url, 'http://example.com/')

    @sync
    async def test_goto_blank(self):
        response = await self.page.goto('about:blank')
        self.assertIsNone(response)

    @sync
    async def test_goto_documentloaded(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='documentloaded')
        self.assertIn(response.status, [200, 304])

    @sync
    async def test_goto_networkidle(self):
        with self.assertRaises(ValueError):
            await self.page.goto(self.url + 'empty', waitUntil='networkidle')

    @sync
    async def test_nav_networkidle0(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='networkidle0')
        self.assertIn(response.status, [200, 304])

    @sync
    async def test_nav_networkidle2(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='networkidle2')
        self.assertIn(response.status, [200, 304])

    @sync
    async def test_goto_bad_url(self):
        with self.assertRaises(NetworkError):
            await self.page.goto('asdf')

    @sync
    async def test_goto_bad_resource(self):
        with self.assertRaises(PageError):
            await self.page.goto('http://localhost:44123')

    @sync
    async def test_get(self):
        self.assertEqual(await self.page.title(), 'main')
        self.assertEqual(self.page.url, self.url)
        self.elm = await self.page.querySelector('h1#hello')
        self.assertTrue(self.elm)
        await self.page.goto('about:blank')
        self.assertEqual(self.page.url, 'about:blank')

    @sync
    async def test_timeout(self):
        with self.assertRaises(TimeoutError):
            await self.page.goto(self.url + 'long', timeout=100)

    @sync
    async def test_no_timeout(self):
        await self.page.goto(self.url + 'long', timeout=0)

    @sync
    async def test_get_https(self):
        await self.page.goto('https://example.com/')
        self.assertEqual(self.page.url, 'https://example.com/')

    @sync
    async def test_plain_text_depr(self):
        with self.assertWarns(DeprecationWarning):
            text = await self.page.plainText()
        self.assertEqual(text.split(), ['Hello', 'link1', 'link2'])

    @sync
    async def test_content(self):
        html = await self.page.content()
        self.assertEqual(html.replace('\n', ''), BASE_HTML.replace('\n', ''))

    @sync
    async def test_evaluate(self):
        await self.page.evaluate('window.__injected = 12;')
        injected = await self.page.evaluate('() => window.__injected')
        self.assertEqual(injected, 12)

    @sync
    async def test_evaluate_return_value(self):
        result = await self.page.evaluate('1 + 2')
        self.assertEqual(result, 3)

    @sync
    async def test_evaluate_return_value_with_semicolon(self):
        result = await self.page.evaluate('1 + 5;')
        self.assertEqual(result, 6)

    @sync
    async def test_evaluate_return_value_with_comment(self):
        result = await self.page.evaluate('2 + 5;\n//some comment')
        self.assertEqual(result, 7)

    @sync
    async def test_evaluate_multi_expression(self):
        result = await self.page.evaluate('''
let a = 2;
let b = 3;
a + b
        ''')
        self.assertEqual(result, 5)

    @sync
    async def test_evaluate_error(self):
        with self.assertRaises(ElementHandleError):
            await self.page.evaluate('not.existing.object')

    @sync
    async def test_evaluate_func(self):
        result = await self.page.evaluate('() => 3 * 7')
        self.assertEqual(result, 21)

    @unittest.skip('Promise is not awaited')
    @sync
    async def test_evaluate_func_promise(self):
        result = await self.page.evaluate('() => Promise.resolve(8 * 7)')
        self.assertEqual(result, 56)

    @sync
    async def test_evaluate_func_args(self):
        result = await self.page.evaluate('(a, b) => a * b', 9, 3)
        self.assertEqual(result, 27)

    @sync
    async def test_evaluate_func_complex_object(self):
        obj = {'a': 1, 'b': 'b'}
        result = await self.page.evaluate('(a) => a', obj)
        self.assertEqual(result, obj)

    @sync
    async def test_evaluate_func_return_none(self):
        result = await self.page.evaluate('() => NaN')
        self.assertIs(result, None)

    @sync
    async def test_evaluate_func_return_minus_zero(self):
        result = await self.page.evaluate('() => -0')
        self.assertEqual(result, -0)

    @sync
    async def test_evaluate_func_return_inf(self):
        result = await self.page.evaluate('() => Infinity')
        self.assertEqual(result, math.inf)

    @sync
    async def test_evaluate_func_return_inf_minus(self):
        result = await self.page.evaluate('() => -Infinity')
        self.assertEqual(result, -math.inf)

    @sync
    async def test_evaluate_func_return_undefined(self):
        result = await self.page.evaluate('() => undefined')
        self.assertEqual(result, None)

    @sync
    async def test_evaluate_func_return_null(self):
        result = await self.page.evaluate('() => null')
        self.assertEqual(result, None)

    @sync
    async def test_evaluate_func_error(self):
        with self.assertRaises(ElementHandleError):
            await self.page.evaluate('() => not.existing.object')

    @sync
    async def test_primitive_handle(self):
        handle = await self.page.evaluateHandle('() => 5')
        is_five = await self.page.evaluate('(a) => Object.is(a, 5)', handle)
        self.assertTrue(is_five)

    @sync
    async def test_jshandle_json(self):
        handle1 = await self.page.evaluateHandle('() => ({foo: "bar"})')
        json = await handle1.jsonValue()
        self.assertEqual(json, {'foo': 'bar'})

    @sync
    async def test_jshandle_get_property(self):
        handle1 = await self.page.evaluateHandle(
            '() => ({one: 1, two: 2, three: 3})'
        )
        handle2 = await handle1.getProperty('two')
        self.assertEqual(await handle2.jsonValue(), 2)

    @sync
    async def test_jshandle_get_properties(self):
        handle1 = await self.page.evaluateHandle('() => ({foo: "bar"})')
        properties = await handle1.getProperties()
        foo = properties.get('foo')
        self.assertTrue(foo)
        self.assertEqual(await foo.jsonValue(), 'bar')

    @sync
    async def test_element(self):
        elm = await self.page.querySelector('h1')
        text = await self.page.evaluate(
            '(element) => element.textContent', elm)
        self.assertEqual('Hello', text)

    @sync
    async def test_elements(self):
        elms = await self.page.querySelectorAll('a')
        self.assertEqual(len(elms), 2)
        elm1 = elms[0]
        elm2 = elms[1]
        func = 'elm => elm.id'
        # 3.5 does not keep node order.
        if sys.version_info >= (3, 6):
            self.assertEqual(await self.page.evaluate(func, elm1), 'link1')
            self.assertEqual(await self.page.evaluate(func, elm2), 'link2')

    @sync
    async def test_elements_eval(self):
        ln = await self.page.querySelectorAllEval('a', 'nodes => nodes.length')
        self.assertEqual(ln, 2)

    @sync
    async def test_element_inner_html(self):
        elm = await self.page.querySelector('h1')
        text = await self.page.evaluate('(element) => element.innerHTML', elm)
        self.assertEqual('Hello', text)

    @sync
    async def test_element_outer_html(self):
        elm = await self.page.querySelector('h1')
        text = await self.page.evaluate('(element) => element.outerHTML', elm)
        self.assertEqual('<h1 id="hello">Hello</h1>', text)

    @sync
    async def test_element_attr(self):
        _id = await self.page.querySelectorEval('h1', ('(elm) => elm.id'))
        self.assertEqual('hello', _id)

    @sync
    async def test_element_handle_J(self):
        await self.page.setContent('''
<html><body><div class="second"><div class="inner">A</div></div></body></html>
        ''')
        html = await self.page.J('html')
        second = await html.J('.second')
        inner = await second.J('.inner')
        content = await self.page.evaluate('e => e.textContent', inner)
        self.assertEqual(content, 'A')

    @sync
    async def test_element_handle_J_none(self):
        await self.page.setContent('''
<html><body><div class="second"><div class="inner">A</div></div></body></html>
        ''')
        html = await self.page.J('html')
        second = await html.J('.third')
        self.assertIsNone(second)

    @sync
    async def test_element_handle_JJ(self):
        await self.page.setContent('''
<html><body><div>A</div><br/><div>B</div></body></html>
        ''')
        html = await self.page.J('html')
        elements = await html.JJ('div')
        self.assertEqual(len(elements), 2)
        if sys.version_info >= (3, 6):
            result = []
            for elm in elements:
                result.append(
                    await self.page.evaluate('(e) => e.textContent', elm)
                )
            self.assertEqual(result, ['A', 'B'])

    @sync
    async def test_element_handle_JJ_empty(self):
        await self.page.setContent('''
<html><body><span>A</span><br/><span>B</span></body></html>
        ''')
        html = await self.page.J('html')
        elements = await html.JJ('div')
        self.assertEqual(len(elements), 0)

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
    async def test_elm_tap(self):
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.tap()
        await asyncio.sleep(0.05)
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
            'document.cookie = "username=John Doe"'
        )
        cookies = await self.page.cookies()
        self.assertEqual(cookies, [{
            'name': 'username',
            'value': 'John Doe',
            'domain': 'localhost',
            'path': '/',
            'expires': -1,
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
            'expires': -1,
            'size': 14,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }, {
            'name': 'username',
            'value': 'John Doe',
            'domain': 'localhost',
            'path': '/',
            'expires': -1,
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
            'expires': -1,
            'size': 14,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])

    @sync
    async def test_redirect(self):
        await self.page.goto(self.url + 'redirect1')
        await self.page.waitForSelector('h1#red2')
        text = await self.page.evaluate('() => document.body.innerText')
        self.assertEqual(text, 'redirect2')

    @sync
    async def test_script_tag_error(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(ValueError):
            await self.page.addScriptTag('/static/injectedfile.js')

    @sync
    async def test_script_tag_url(self):
        await self.page.goto(self.url + 'empty')
        scriptHandle = await self.page.addScriptTag(url='/static/injectedfile.js')  # noqa: E501
        self.assertIsNotNone(scriptHandle.asElement())
        self.assertEqual(await self.page.evaluate('() => window.__injected'), 42)  # noqa: E501

    @sync
    async def test_script_tag_path(self):
        curdir = Path(__file__).parent
        path = str(curdir / 'static' / 'injectedfile.js')
        await self.page.goto(self.url + 'empty')
        scriptHanlde = await self.page.addScriptTag(path=path)
        self.assertIsNotNone(scriptHanlde.asElement())
        self.assertEqual(await self.page.evaluate('() => window.__injected'), 42)  # noqa: E501

    @sync
    async def test_script_tag_content(self):
        await self.page.goto(self.url + 'empty')
        scriptHandle = await self.page.addScriptTag(content='window.__injected = 35;')  # noqa: E501
        self.assertIsNotNone(scriptHandle.asElement())
        self.assertEqual(await self.page.evaluate('() => window.__injected'), 35)  # noqa: E501

    @sync
    async def test_style_tag_error(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(ValueError):
            await self.page.addStyleTag('/static/injectedstyle.css')

    async def get_bgcolor(self):
        return await self.page.evaluate('() => window.getComputedStyle(document.querySelector("body")).getPropertyValue("background-color")')  # noqa: E501

    @sync
    async def test_style_tag_url(self):
        await self.page.goto(self.url + 'empty')
        self.assertEqual(await self.get_bgcolor(), 'rgba(0, 0, 0, 0)')
        styleHandle = await self.page.addStyleTag(url='/static/injectedstyle.css')  # noqa: E501
        self.assertIsNotNone(styleHandle.asElement())
        self.assertEqual(await self.get_bgcolor(), 'rgb(255, 0, 0)')

    @sync
    async def test_style_tag_path(self):
        curdir = Path(__file__).parent
        path = str(curdir / 'static' / 'injectedstyle.css')
        await self.page.goto(self.url + 'empty')
        self.assertEqual(await self.get_bgcolor(), 'rgba(0, 0, 0, 0)')
        styleHandle = await self.page.addStyleTag(path=path)
        self.assertIsNotNone(styleHandle.asElement())
        self.assertEqual(await self.get_bgcolor(), 'rgb(255, 0, 0)')

    @sync
    async def test_style_tag_content(self):
        await self.page.goto(self.url + 'empty')
        self.assertEqual(await self.get_bgcolor(), 'rgba(0, 0, 0, 0)')
        styleHandle = await self.page.addStyleTag(content=' body {background-color: green;}')  # noqa: E501
        self.assertIsNotNone(styleHandle.asElement())
        self.assertEqual(await self.get_bgcolor(), 'rgb(0, 128, 0)')

    @sync
    async def test_select_error(self):
        await self.page.goto(self.url + 'static/select.html')
        with self.assertRaises(ElementHandleError):
            await self.page.select('body', '')

    @sync
    async def test_select_no_match(self):
        await self.page.goto(self.url + 'static/select.html')
        result = await self.page.select('select', '42', 'abc')
        self.assertEqual(result, [])

    @sync
    async def test_select_match(self):
        await self.page.goto(self.url + 'static/select.html')
        result = await self.page.select('select', 'blue', 'black', 'magenta')
        self.assertEqual(result, ['magenta'])

    @sync
    async def test_select_match_deselect(self):
        await self.page.goto(self.url + 'static/select.html')
        await self.page.select('select', 'blue', 'black', 'magenta')
        await self.page.select('select')
        result = await self.page.Jeval(
            'select',
            'select => Array.from(select.options).every(option => !option.selected)',  # noqa: E501
        )
        self.assertTrue(result)

    @sync
    async def test_key_type(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        text = 'Type in this text!'
        await textarea.type(text)
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, text)
        result = await self.page.evaluate('() => result')
        self.assertEqual(result, text)

    @sync
    async def test_key_arrowkey(self):
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.type('textarea', 'Hello World!')
        for char in 'World!':
            await self.page.keyboard.press('ArrowLeft')
        await self.page.keyboard.type('inserted ')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'Hello inserted World!')

        await self.page.keyboard.down('Shift')
        for char in 'inserted ':
            await self.page.keyboard.press('ArrowLeft')
        await self.page.keyboard.up('Shift')
        await self.page.keyboard.press('Backspace')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'Hello World!')

    @sync
    async def test_key_press_element_handle(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        await textarea.press('a', text='f')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'f')

        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => e.preventDefault(), true)'  # noqa: E501
        )
        await textarea.press('a', text='y')
        self.assertEqual(result, 'f')

    @sync
    async def test_key_send_char(self):
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.focus('textarea')
        await self.page.keyboard.sendCharacter('朝')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, '朝')

        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => e.preventDefault(), true)'  # noqa: E501
        )
        await self.page.keyboard.sendCharacter('a')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, '朝a')

    @sync
    async def test_key_modifiers(self):
        keyboard = self.page.keyboard
        self.assertEqual(keyboard._modifiers, 0)
        await keyboard.down('Shift')
        self.assertEqual(keyboard._modifiers, 8)
        await keyboard.down('Alt')
        self.assertEqual(keyboard._modifiers, 9)
        await keyboard.up('Shift')
        self.assertEqual(keyboard._modifiers, 1)
        await keyboard.up('Alt')
        self.assertEqual(keyboard._modifiers, 0)

    @sync
    async def test_resize_textarea(self):
        await self.page.goto(self.url + 'static/textarea.html')
        get_dimensions = '''
    function () {
      const rect = document.querySelector('textarea').getBoundingClientRect();
      return {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height
      };
    }
        '''

        dimensions = await self.page.evaluate(get_dimensions)
        x = dimensions['x']
        y = dimensions['y']
        width = dimensions['width']
        height = dimensions['height']
        mouse = self.page.mouse
        await mouse.move(x + width - 4, y + height - 4)
        await mouse.down()
        await mouse.move(x + width + 100, y + height + 100)
        await mouse.up()
        new_dimensions = await self.page.evaluate(get_dimensions)
        self.assertEqual(new_dimensions['width'], width + 104)
        self.assertEqual(new_dimensions['height'], height + 104)

    @sync
    async def test_key_type_long(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        text = 'This text is two lines.\\nThis is character 朝.'
        await textarea.type(text)
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, text)
        result = await self.page.evaluate('() => result')
        self.assertEqual(result, text)

    @sync
    async def test_key_location(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => window.keyLocation = e.location, true)'  # noqa: E501
        )

        await textarea.press('Digit5')
        self.assertEqual(await self.page.evaluate('keyLocation'), 0)

        await textarea.press('ControlLeft')
        self.assertEqual(await self.page.evaluate('keyLocation'), 1)

        await textarea.press('ControlRight')
        self.assertEqual(await self.page.evaluate('keyLocation'), 2)

        await textarea.press('NumpadSubtract')
        self.assertEqual(await self.page.evaluate('keyLocation'), 3)

    @sync
    async def test_key_unknown(self):
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('NotARealKey')
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('ё')
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('😊')

    @sync
    async def test_targets(self):
        targets = self.browser.targets()
        _list = [target for target in targets
                 if target.type() == 'page' and target.url() == 'about:blank']
        self.assertTrue(any(_list))

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


class TestWaitForSelector(BaseTestCase):
    addElement = 'tag=>document.body.appendChild(document.createElement(tag))'

    @sync
    async def test_wait_for_selector_immediate(self):
        await self.page.goto(self.url + 'empty')
        frame = self.page.mainFrame
        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('*', interval=50))
        fut.add_done_callback(lambda fut: result.append(True))
        await asyncio.sleep(0.1)
        self.assertTrue(result)

        result.clear()
        await frame.evaluate(self.addElement, 'div')
        fut = asyncio.ensure_future(frame.waitForSelector('div', interval=50))
        fut.add_done_callback(lambda fut: result.append(True))
        await asyncio.sleep(0.1)
        self.assertTrue(result)

    @sync
    async def test_wait_for_selector_after_node_appear(self):
        await self.page.goto(self.url + 'empty')
        frame = self.page.mainFrame

        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('div', interval=50))
        fut.add_done_callback(lambda fut: result.append(True))
        self.assertEqual(await frame.evaluate('() => 42'), 42)
        await asyncio.sleep(0.1)
        self.assertFalse(result)
        await frame.evaluate(self.addElement, 'br')
        await asyncio.sleep(0.1)
        self.assertFalse(result)
        await frame.evaluate(self.addElement, 'div')
        await asyncio.sleep(0.1)
        self.assertTrue(result)

    @sync
    async def test_wait_for_selector_inner_html(self) -> None:
        await self.page.goto(self.url + 'empty')
        fut = asyncio.ensure_future(self.page.waitForSelector('h3 div'))
        await self.page.evaluate(self.addElement, 'span')
        await self.page.evaluate('() => document.querySelector("span").innerHTML = "<h3><div></div></h3>"')  # noqa: E501
        await fut

    @sync
    async def test_wait_for_selector_fail(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('() => document.querySelector = null')  # noqa: E501
        with self.assertRaises(ElementHandleError):
            await self.page.waitForSelector('*')

    @sync
    async def test_wait_for_selector_visible(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', visible=True, interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent(
            '<div style="display: none; visibility: hidden;">1</div>'
        )
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_visible_ininer(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div#inner', visible=True, interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent(
            '<div style="display: none; visibility: hidden;">'
            '<div id="inner">hi</div></div>'
        )
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_hidden(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True, interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.setProperty("visibility", "hidden")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_display_none(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True, interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.setProperty("display", "none")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_remove(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        await self.page.setContent('<div></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True, interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").remove()')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_timeout(self) -> None:
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(TimeoutError):
            await self.page.waitForSelector('div', timeout=10)

    @sync
    async def test_wait_for_selector_node_mutation(self) -> None:
        await self.page.goto(self.url + 'empty')
        div = []
        fut = asyncio.ensure_future(
            self.page.waitForSelector('.cls', interval=50))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent('<div class="noCls"></div>')
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate(
            '() => document.querySelector("div").className="cls"'
        )
        await asyncio.sleep(0.1)
        self.assertTrue(div)


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
    async def test_inject_file(self):  # deprecated
        tmp_file = Path('tmp.js')
        with tmp_file.open('w') as f:
            f.write('''
() => document.body.appendChild(document.createElement("section"))
            '''.strip())
        with self.assertWarns(DeprecationWarning):
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

    @unittest.skip('This test fails')
    @sync
    async def test_interception_enable(self):
        await self.page.setRequestInterceptionEnabled(True)
        await self.page.goto(self.url)

    @sync
    async def test_auth(self):
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 401)
        await self.page.authenticate({'username': 'user', 'password': 'pass'})
        response = await self.page.goto(self.url + 'auth')
        self.assertIn(response.status, [200, 304])

    @sync
    async def test_metrics(self):
        await self.page.goto('about:blank')
        metrics = await self.page.metrics()
        metrics_to_check = set([
            'Timestamp',
            'Documents',
            'Frames',
            'JSEventListeners',
            'Nodes',
            'LayoutCount',
            'RecalcStyleCount',
            'LayoutDuration',
            'RecalcStyleDuration',
            'ScriptDuration',
            'TaskDuration',
            'JSHeapUsedSize',
            'JSHeapTotalSize',
        ])
        for name, value in metrics.items():
            self.assertTrue(name in metrics_to_check)
            self.assertTrue(value >= 0)
            metrics_to_check.remove(name)
        self.assertEqual(len(metrics_to_check), 0)

    @sync
    async def test_offline_mode(self):
        await self.page.setOfflineMode(True)
        with self.assertRaises(PageError):
            await self.page.goto(self.url)
        await self.page.setOfflineMode(False)
        res = await self.page.reload()
        self.assertEqual(res.status, 304)

    @sync
    async def test_no_await_check_just_call(self):
        await self.page.setExtraHTTPHeaders({'a': 'b'})
        await self.page.setContent('')
        await self.page.setJavaScriptEnabled(True)
        await self.page.emulateMedia()
        await self.page.evaluateOnNewDocument('() => 1 + 2')
