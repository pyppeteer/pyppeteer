#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import json
import logging
import math
from pathlib import Path
import sys
import time
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.errors import ElementHandleError, NetworkError, PageError
from pyppeteer.errors import PyppeteerError
from pyppeteer.util import get_free_port

from base import BaseTestCase, DEFAULT_OPTIONS
from frame_utils import attachFrame, detachFrame, dumpFrames, navigateFrame
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
    async def test_evaluate(self):
        await self.page.evaluate('window.__injected = 12;')
        injected = await self.page.evaluate('() => window.__injected')
        self.assertEqual(injected, 12)

    @sync
    async def test_evaluate_return_value(self):
        result = await self.page.evaluate('1 + 2')
        self.assertEqual(result, 3)

    @sync
    async def test_evaluate_force_expression(self):
        result = await self.page.evaluate(
            '() => null;\n1 + 2;', force_expr=True)
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

    @unittest.skip('Cannot pass this test. see puppeteer #1510.')
    @sync
    async def test_evaluate_func_null_field(self):
        result = await self.page.evaluate('{a: undefined}')
        self.assertEqual(result, {})

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
    async def test_query_elector(self):
        elm = await self.page.querySelector('h1')
        text = await self.page.evaluate(
            '(element) => element.textContent', elm)
        self.assertEqual('Hello', text)

    @sync
    async def test_query_elector_not_found(self):
        elm = await self.page.querySelector('span')
        self.assertIsNone(elm)

    @sync
    async def test_query_selector_all(self):
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
    async def test_query_selector_all_not_found(self):
        elms = await self.page.querySelectorAll('span')
        self.assertEqual(elms, [])

    @sync
    async def test_query_elector_eval(self):
        result = await self.page.querySelectorEval(
            'h1', '(elm) => elm.textContent')
        self.assertEqual(result, 'Hello')

    @sync
    async def test_query_elector_eval_not_found(self):
        with self.assertRaises(PageError):
            await self.page.querySelectorEval('span', '(elm) => elm')

    @sync
    async def test_query_selector_all_eval(self):
        ln = await self.page.querySelectorAllEval('a', 'nodes => nodes.length')
        self.assertEqual(ln, 2)

    @sync
    async def test_query_selector_all_eval_not_fount(self):
        ln = await self.page.querySelectorAllEval(
            'span', 'nodes => nodes.length')
        self.assertEqual(ln, 0)

    @sync
    async def test_page_xpath(self):
        await self.page.setContent('<section>test</section>')
        element = await self.page.xpath('/html/body/section')
        self.assertTrue(element)

    @sync
    async def test_page_xpath_alias(self):
        await self.page.setContent('<section>test</section>')
        element = await self.page.Jx('/html/body/section')
        self.assertTrue(element)

    @sync
    async def test_page_xpath_not_found(self):
        element = await self.page.xpath('/html/body/no-such-tag')
        self.assertEqual(element, [])

    @sync
    async def test_page_xpath_multiple(self):
        await self.page.setContent('<div></div><div></div>')
        element = await self.page.xpath('/html/body/div')
        self.assertEqual(len(element), 2)

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
        _id = await self.page.querySelectorEval('h1', '(elm) => elm.id')
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
    async def test_element_handle_xpath(self):
        await self.page.setContent(
            '<html><body><div class="second"><div class="inner">A</div></div></body></html>'  # noqa: E501
        )
        html = await self.page.querySelector('html')
        second = await html.xpath('./body/div[contains(@class, \'second\')]')
        inner = await second[0].xpath('./div[contains(@class, \'inner\')]')
        content = await self.page.evaluate('(e) => e.textContent', inner[0])
        self.assertEqual(content, 'A')

    @sync
    async def test_element_handle_xpath_not_found(self):
        await self.page.goto(self.url + 'empty')
        html = await self.page.querySelector('html')
        element = await html.xpath('/div[contains(@class, \'third\')]')
        self.assertEqual(element, [])

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
    async def test_select(self):
        await self.page.goto(self.url + 'static/select.html')
        value = await self.page.select('select', 'blue')
        self.assertEqual(value, ['blue'])
        _input = await self.page.evaluate('result.onInput')
        self.assertEqual(_input, ['blue'])
        change = await self.page.evaluate('result.onChange')
        self.assertEqual(change, ['blue'])

        _input = await self.page.evaluate('result.onBubblingInput')
        self.assertEqual(_input, ['blue'])
        change = await self.page.evaluate('result.onBubblingChange')
        self.assertEqual(change, ['blue'])

    @sync
    async def test_select_multiple(self):
        await self.page.goto(self.url + 'static/select.html')
        await self.page.evaluate('makeMultiple();')
        values = await self.page.select('select', 'blue', 'green', 'red')
        self.assertEqual(values, ['blue', 'green', 'red'])
        _input = await self.page.evaluate('result.onInput')
        self.assertEqual(_input, ['blue', 'green', 'red'])
        change = await self.page.evaluate('result.onChange')
        self.assertEqual(change, ['blue', 'green', 'red'])

    @sync
    async def test_select_not_select_element(self):
        await self.page.goto(self.url + 'static/select.html')
        with self.assertRaises(ElementHandleError):
            await self.page.select('body', '')

    @sync
    async def test_select_no_match(self):
        await self.page.goto(self.url + 'static/select.html')
        values = await self.page.select('select', 'abc', 'def')
        self.assertEqual(values, [])

    @sync
    async def test_select_not_multiple(self):
        await self.page.goto(self.url + 'static/select.html')
        values = await self.page.select('select', 'blue', 'green', 'red')
        self.assertEqual(len(values), 1)

    @sync
    async def test_select_no_value(self):
        await self.page.goto(self.url + 'static/select.html')
        values = await self.page.select('select')
        self.assertEqual(values, [])

    @sync
    async def test_select_deselect(self):
        await self.page.goto(self.url + 'static/select.html')
        await self.page.select('select', 'blue', 'green', 'red')
        await self.page.select('select')
        result = await self.page.Jeval(
            'select',
            'elm => Array.from(elm.options).every(option => !option.selected)'
        )
        self.assertTrue(result)

    @sync
    async def test_select_deselect_multiple(self):
        await self.page.goto(self.url + 'static/select.html')
        await self.page.evaluate('makeMultiple();')
        await self.page.select('select', 'blue', 'green', 'red')
        await self.page.select('select')
        result = await self.page.Jeval(
            'select',
            'elm => Array.from(elm.options).every(option => !option.selected)'
        )
        self.assertTrue(result)

    @sync
    async def test_select_nonstring(self):
        await self.page.goto(self.url + 'static/select.html')
        with self.assertRaises(TypeError):
            await self.page.select('select', 12)

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
    async def test_cookie_blank_page(self):
        await self.page.goto('about:blank')
        with self.assertRaises(NetworkError):
            await self.page.setCookie({'name': 'example-cookie', 'value': 'a'})

    @sync
    async def test_cookie_blank_page2(self):
        with self.assertRaises(PageError):
            await self.page.setCookie(
                {'name': 'example-cookie', 'value': 'best'},
                {'url': 'about:blank',
                 'name': 'example-cookie-blank',
                 'value': 'best'}
            )

    @sync
    async def test_cookie_data_url_page(self):
        await self.page.goto('data:,hello')
        with self.assertRaises(NetworkError):
            await self.page.setCookie({'name': 'example-cookie', 'value': 'a'})

    @sync
    async def test_cookie_data_url_page2(self):
        with self.assertRaises(PageError):
            await self.page.setCookie(
                {'name': 'example-cookie', 'value': 'best'},
                {'url': 'data:,hello',
                 'name': 'example-cookie-blank',
                 'value': 'best'}
            )

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

    @sync
    async def test_expose_function(self):
        await self.page.goto(self.url + 'empty')
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        result = await self.page.evaluate('(a, b) => compute(a, b)', 9, 4)
        self.assertEqual(result, 36)

    @sync
    async def test_expose_function_other_page(self):
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        await self.page.goto(self.url + 'empty')
        result = await self.page.evaluate('(a, b) => compute(a, b)', 9, 4)
        self.assertEqual(result, 36)

    @sync
    async def test_request_interception(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            self.assertIn('empty', req.url)
            self.assertTrue(req.headers.get('user-agent'))
            self.assertEqual(req.method, 'GET')
            self.assertEqual(req.resourceType, 'document')
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        res = await self.page.goto(self.url + 'empty')
        self.assertIn(res.status, [200, 304])

    @sync
    async def test_request_interception_stop(self):
        await self.page.setRequestInterception(True)
        self.page.once('request',
                       lambda req: asyncio.ensure_future(req.continue_()))
        await self.page.goto(self.url + 'empty')
        await self.page.setRequestInterception(False)
        await self.page.goto(self.url + 'empty')

    @sync
    async def test_request_interception_custom_header(self):
        await self.page.setExtraHTTPHeaders({'foo': 'bar'})
        await self.page.setRequestInterception(True)

        async def request_check(req):
            self.assertEqual(req.headers['foo'], 'bar')
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        res = await self.page.goto(self.url + 'empty')
        self.assertIn(res.status, [200, 304])

    @sync
    async def test_request_interception_custom_referer_header(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setExtraHTTPHeaders({'referer': self.url + 'empty'})
        await self.page.setRequestInterception(True)

        async def request_check(req):
            self.assertEqual(req.headers['referer'], self.url + 'empty')
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        res = await self.page.goto(self.url + 'empty')
        self.assertIn(res.status, [200, 304])

    @sync
    async def test_request_interception_abort_main(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            await req.abort()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        with self.assertRaises(PageError) as cm:
            await self.page.goto(self.url + 'empty')
        self.assertEqual(str(cm.exception), 'net::ERR_FAILED')

    @sync
    async def test_request_interception_abort(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            if req.url.endswith('.css'):
                await req.abort()
            else:
                await req.continue_()

        failedRequests = []
        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        self.page.on('requestfailed', lambda e: failedRequests.append(e))
        res = await self.page.goto(self.url + 'static/one-style.html')
        self.assertTrue(res.ok)
        self.assertIsNone(res.request.failure())
        self.assertEqual(len(failedRequests), 1)

    @sync
    async def test_request_interception_custom_error_code(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            await req.abort('internetdisconnected')

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        failedRequests = []
        self.page.on('requestfailed', lambda req: failedRequests.append(req))
        with self.assertRaises(PageError):
            await self.page.goto(self.url + 'empty')
        self.assertEqual(len(failedRequests), 1)
        failedRequest = failedRequests[0]
        self.assertEqual(
            failedRequest.failure()['errorText'],
            'net::ERR_INTERNET_DISCONNECTED',
        )

    @sync
    async def test_request_respond(self):
        await self.page.setRequestInterception(True)

        async def interception(req):
            await req.respond({
                'status': 201,
                'headers': {'foo': 'bar'},
                'body': 'intercepted',
            })

        self.page.on(
            'request', lambda req: asyncio.ensure_future(interception(req)))
        response = await self.page.goto(self.url + 'empty')
        self.assertEqual(response.status, 201)
        self.assertEqual(response.headers['foo'], 'bar')
        body = await self.page.evaluate('() => document.body.textContent')
        self.assertEqual(body, 'intercepted')


class TestFrames(BaseTestCase):
    @sync
    async def test_frame_nested(self):
        await self.page.goto(self.url + 'static/nested-frames.html')
        dumped_frames = dumpFrames(self.page.mainFrame)
        try:
            self.assertEqual(
                dumped_frames, '''
http://localhost:{port}/static/nested-frames.html
    http://localhost:{port}/static/two-frames.html
        http://localhost:{port}/static/frame.html
        http://localhost:{port}/static/frame.html
    http://localhost:{port}/static/frame.html
                '''.format(port=self.port).strip()
            )
        except AssertionError:
            print('\n== Nested frame test failed, which is unstable ==')
            print(dumpFrames(self.page.mainFrame))

    @sync
    async def test_frame_events(self):
        await self.page.goto(self.url + 'empty')
        attachedFrames = []
        self.page.on('frameattached', lambda f: attachedFrames.append(f))
        await attachFrame(self.page, 'frame1', './static/frame.html')
        self.assertEqual(len(attachedFrames), 1)
        self.assertIn('static/frame.html', attachedFrames[0].url)

        navigatedFrames = []
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await navigateFrame(self.page, 'frame1', '/empty')
        self.assertEqual(len(navigatedFrames), 1)
        self.assertIn('empty', navigatedFrames[0].url)

        detachedFrames = []
        self.page.on('framedetached', lambda f: detachedFrames.append(f))
        await detachFrame(self.page, 'frame1')
        self.assertEqual(len(detachedFrames), 1)
        self.assertTrue(detachedFrames[0].isDetached())

    @sync
    async def test_frame_events_main(self):
        # no attach/detach events should be emitted on main frame
        events = []
        navigatedFrames = []
        self.page.on('frameattached', lambda f: events.append(f))
        self.page.on('framedetached', lambda f: events.append(f))
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await self.page.goto(self.url + 'empty')
        self.assertFalse(events)
        self.assertEqual(len(navigatedFrames), 1)

    @sync
    async def test_frame_events_child(self):
        attachedFrames = []
        detachedFrames = []
        navigatedFrames = []
        self.page.on('frameattached', lambda f: attachedFrames.append(f))
        self.page.on('framedetached', lambda f: detachedFrames.append(f))
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await self.page.goto(self.url + 'static/nested-frames.html')
        self.assertEqual(len(attachedFrames), 4)
        self.assertEqual(len(detachedFrames), 0)
        self.assertEqual(len(navigatedFrames), 5)

        attachedFrames.clear()
        detachedFrames.clear()
        navigatedFrames.clear()
        await self.page.goto(self.url + 'empty')
        self.assertEqual(len(attachedFrames), 0)
        self.assertEqual(len(detachedFrames), 4)
        self.assertEqual(len(navigatedFrames), 1)

    @sync
    async def test_frame_name(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'FrameId', self.url + 'empty')
        await asyncio.sleep(0.1)
        await self.page.evaluate(
            '''(url) => {
                const frame = document.createElement('iframe');
                frame.name = 'FrameName';
                frame.src = url;
                document.body.appendChild(frame);
                return new Promise(x => frame.onload = x);
            }''', self.url + 'empty')
        await asyncio.sleep(0.1)

        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        frame3 = self.page.frames[2]
        self.assertEqual(frame1.name, '')
        self.assertEqual(frame2.name, 'FrameId')
        self.assertEqual(frame3.name, 'FrameName')

    @sync
    async def test_frame_parent(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        await attachFrame(self.page, 'frame2', self.url + 'empty')
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        frame3 = self.page.frames[2]
        self.assertEqual(frame1, self.page.mainFrame)
        self.assertEqual(frame1.parentFrame, None)
        self.assertEqual(frame2.parentFrame, frame1)
        self.assertEqual(frame3.parentFrame, frame1)


class TestTracing(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.outfile = Path(__file__).parent / 'trace.json'
        if self.outfile.is_file():
            self.outfile.unlink()

    def tearDown(self):
        if self.outfile.is_file():
            self.outfile.unlink()
        super().tearDown()

    @sync
    async def test_tracing(self):
        await self.page.tracing.start({
            'path': str(self.outfile)
        })
        await self.page.goto(self.url)
        await self.page.tracing.stop()
        self.assertTrue(self.outfile.is_file())

    @sync
    async def test_custom_categories(self):
        await self.page.tracing.start({
            'path': str(self.outfile),
            'categories': ['disabled-by-default-v8.cpu_profiler.hires'],
        })
        await self.page.tracing.stop()
        self.assertTrue(self.outfile.is_file())
        with self.outfile.open() as f:
            trace_json = json.load(f)
        self.assertIn(
            'disabled-by-default-v8.cpu_profiler.hires',
            trace_json['metadata']['trace-config'],
        )

    @sync
    async def test_tracing_two_page_error(self):
        await self.page.tracing.start({'path': str(self.outfile)})
        new_page = await self.browser.newPage()
        with self.assertRaises(NetworkError):
            await new_page.tracing.start({'path': str(self.outfile)})
        await new_page.close()
        await self.page.tracing.stop()


class TestCDPSession(BaseTestCase):
    @sync
    async def test_create_session(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        await client.send('Runtime.evaluate',
                          {'expression': 'window.foo = "bar"'})
        foo = await self.page.evaluate('window.foo')
        self.assertEqual(foo, 'bar')

    @sync
    async def test_send_event(self):
        client = await self.page.target.createCDPSession()
        await client.send('Network.enable')
        events = []
        client.on('Network.requestWillBeSent', lambda e: events.append(e))
        await self.page.goto(self.url + 'empty')
        self.assertEqual(len(events), 1)

    @sync
    async def test_enable_disable_domain(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        await client.send('Debugger.enable')
        await self.page.coverage.startJSCoverage()
        await self.page.coverage.stopJSCoverage()

    @sync
    async def test_detach(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        evalResponse = await client.send(
            'Runtime.evaluate', {'expression': '1 + 2', 'returnByValue': True})
        self.assertEqual(evalResponse['result']['value'], 3)

        await client.detach()
        with self.assertRaises(NetworkError):
            await client.send(
                'Runtime.evaluate',
                {'expression': '1 + 3', 'returnByValue': True}
            )


class TestJSCoverage(BaseTestCase):
    @sync
    async def test_js_coverage(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/simple.html')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertIn('/jscoverage/simple.html', coverage[0]['url'])
        self.assertEqual(coverage[0]['ranges'], [
            {'start': 0, 'end': 17},
            {'start': 35, 'end': 61},
        ])

    @sync
    async def test_js_coverage_source_url(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/sourceurl.html')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]['url'], 'nicename.js')

    @sync
    async def test_js_coverage_ignore_empty(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(coverage, [])

    @sync
    async def test_js_coverage_multiple_script(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 2)
        coverage.sort(key=lambda cov: cov['url'])
        self.assertIn('/jscoverage/script1.js', coverage[0]['url'])
        self.assertIn('/jscoverage/script2.js', coverage[1]['url'])

    @sync
    async def test_js_coverage_ranges(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/ranges.html')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 1)
        entry = coverage[0]
        self.assertEqual(len(entry['ranges']), 1)
        range = entry['ranges'][0]
        self.assertEqual(
            entry['text'][range['start']:range['end']],
            'console.log(\'used!\');',
        )

    @sync
    async def test_js_coverage_condition(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/involved.html')
        coverage = await self.page.coverage.stopJSCoverage()
        expected_range = [
            {'start': 0, 'end': 35},
            {'start': 50, 'end': 100},
            {'start': 107, 'end': 141},
            {'start': 148, 'end': 160},
            {'start': 168, 'end': 207},
        ]
        self.assertEqual(coverage[0]['ranges'], expected_range)

    @sync
    async def test_js_coverage_no_reset_navigation(self):
        await self.page.coverage.startJSCoverage(resetOnNavigation=False)
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 2)

    @sync
    async def test_js_coverage_reset_navigation(self):
        await self.page.coverage.startJSCoverage()  # enabled by default
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        self.assertEqual(len(coverage), 0)


class TestCSSCoverage(BaseTestCase):
    @sync
    async def test_css_coverage(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/simple.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertIn('/csscoverage/simple.html', coverage[0]['url'])
        self.assertEqual(coverage[0]['ranges'], [{'start': 1, 'end': 22}])
        range = coverage[0]['ranges'][0]
        self.assertEqual(
            coverage[0]['text'][range['start']:range['end']],
            'div { color: green; }',
        )

    @sync
    async def test_css_coverage_url(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/sourceurl.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]['url'], 'nicename.css')

    @sync
    async def test_css_coverage_multiple(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 2)
        coverage.sort(key=lambda cov: cov['url'])
        self.assertIn('/csscoverage/stylesheet1.css', coverage[0]['url'])
        self.assertIn('/csscoverage/stylesheet2.css', coverage[1]['url'])

    @sync
    async def test_css_coverage_no_coverage(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/unused.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]['url'], 'unused.css')
        self.assertEqual(coverage[0]['ranges'], [])

    @sync
    async def test_css_coverage_media(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/media.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 1)
        self.assertIn('/csscoverage/media.html', coverage[0]['url'])
        self.assertEqual(coverage[0]['ranges'], [{'start': 17, 'end': 38}])

    @sync
    async def test_css_coverage_complicated(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/involved.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 1)
        range = coverage[0]['ranges']
        self.assertEqual(range, [
            {'start': 20, 'end': 168},
            {'start': 198, 'end': 304},
        ])

    @unittest.skip('Cannot pass this test.')
    @sync
    async def test_css_ignore_injected_css(self):
        await self.page.goto(self.url + 'empty')
        await self.page.coverage.startCSSCoverage()
        await self.page.addStyleTag(content='body { margin: 10px; }')
        # trigger style recalc
        margin = await self.page.evaluate(
            '() => window.getComputedStyle(document.body).margin')
        self.assertEqual(margin, '10px')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(coverage, [])

    @sync
    async def test_css_coverage_no_reset_navigation(self):
        await self.page.coverage.startCSSCoverage(resetOnNavigation=False)
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 2)

    @sync
    async def test_css_coverage_reset_navigation(self):
        await self.page.coverage.startCSSCoverage()  # enabled by default
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopCSSCoverage()
        self.assertEqual(len(coverage), 0)


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
        with self.assertLogs('pyppeteer', logging.WARN) as log:
            await self.page.injectFile(str(tmp_file))
            self.assertIn('deprecated', log.records[0].msg)
        await self.page.waitForSelector('section')
        self.assertIsNotNone(await self.page.J('section'))
        tmp_file.unlink()

    @sync
    async def test_auth(self):
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 401)
        await self.page.authenticate({'username': 'user', 'password': 'pass'})
        response = await self.page.goto(self.url + 'auth')
        self.assertIn(response.status, [200, 304])

    @sync
    async def test_no_await_check_just_call(self):
        await self.page.setExtraHTTPHeaders({'a': 'b'})
        await self.page.setContent('')
        await self.page.setJavaScriptEnabled(True)
        await self.page.emulateMedia()
        await self.page.evaluateOnNewDocument('() => 1 + 2')


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
