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
from pathlib import Path
import time
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.errors import ElementHandleError, NetworkError, PageError
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
