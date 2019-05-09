#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import math
import os
from pathlib import Path
import sys
import time
import unittest

from syncer import sync

from pyppeteer.errors import ElementHandleError, NetworkError, PageError
from pyppeteer.errors import TimeoutError

from .base import BaseTestCase
from .frame_utils import attachFrame
from .utils import waitEvent

iPhone = {
    'name': 'iPhone 6',
    'userAgent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1',  # noqa: E501
    'viewport': {
        'width': 375,
        'height': 667,
        'deviceScaleFactor': 2,
        'isMobile': True,
        'hasTouch': True,
        'isLandscape': False,
    }
}


class TestEvaluate(BaseTestCase):
    @sync
    async def test_evaluate(self):
        result = await self.page.evaluate('() => 7 * 3')
        self.assertEqual(result, 21)

    @sync
    async def test_await_promise(self):
        result = await self.page.evaluate('() => Promise.resolve(8 * 7)')
        self.assertEqual(result, 56)

    @sync
    async def test_error_on_reload(self):
        with self.assertRaises(Exception) as cm:
            await self.page.evaluate('''() => {
                location.reload();
                return new Promise(resolve => {
                    setTimeout(() => resolve(1), 0);
                }
        )}''')
        self.assertIn('Protocol error', cm.exception.args[0])

    @sync
    async def test_after_framenavigation(self):
        frameEvaluation = asyncio.get_event_loop().create_future()

        async def evaluate_frame(frame):
            frameEvaluation.set_result(await frame.evaluate('() => 6 * 7'))

        self.page.on(
            'framenavigated',
            lambda frame: asyncio.ensure_future(evaluate_frame(frame)),
        )
        await self.page.goto(self.url + 'empty')
        await frameEvaluation
        self.assertEqual(frameEvaluation.result(), 42)

    @unittest.skip('Pyppeteer does not support async for exposeFunction')
    @sync
    async def test_inside_expose_function(self):
        async def callController(a, b):
            result = await self.page.evaluate('(a, b) => a + b', a, b)
            return result

        await self.page.exposeFunction(
            'callController',
            lambda *args: asyncio.ensure_future(callController(*args))
        )
        result = await self.page.evaluate(
            'async function() { return await callController(9, 3); }'
        )
        self.assertEqual(result, 27)

    @sync
    async def test_promise_reject(self):
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('() => not.existing.object.property')
        self.assertIn('not is not defined', cm.exception.args[0])

    @sync
    async def test_string_as_error_message(self):
        with self.assertRaises(Exception) as cm:
            await self.page.evaluate('() => { throw "qwerty"; }')
        self.assertIn('qwerty', cm.exception.args[0])

    @sync
    async def test_number_as_error_message(self):
        with self.assertRaises(Exception) as cm:
            await self.page.evaluate('() => { throw 100500; }')
        self.assertIn('100500', cm.exception.args[0])

    @sync
    async def test_return_complex_object(self):
        obj = {'foo': 'bar!'}
        result = await self.page.evaluate('(a) => a', obj)
        self.assertIsNot(result, obj)
        self.assertEqual(result, obj)

    @sync
    async def test_return_nan(self):
        result = await self.page.evaluate('() => NaN')
        self.assertIsNone(result)

    @sync
    async def test_return_minus_zero(self):
        result = await self.page.evaluate('() => -0')
        self.assertEqual(result, -0)

    @sync
    async def test_return_infinity(self):
        result = await self.page.evaluate('() => Infinity')
        self.assertEqual(result, math.inf)

    @sync
    async def test_return_infinity_minus(self):
        result = await self.page.evaluate('() => -Infinity')
        self.assertEqual(result, -math.inf)

    @sync
    async def test_accept_none(self):
        result = await self.page.evaluate(
            '(a, b) => Object.is(a, null) && Object.is(b, "foo")',
            None, 'foo',
        )
        self.assertTrue(result)

    @sync
    async def test_serialize_null_field(self):
        result = await self.page.evaluate('() => ({a: undefined})')
        self.assertEqual(result, {})

    @sync
    async def test_fail_window_object(self):
        self.assertIsNone(await self.page.evaluate('() => window'))
        self.assertIsNone(await self.page.evaluate('() => [Symbol("foo4")]'))

    @sync
    async def test_fail_for_circular_object(self):
        result = await self.page.evaluate('''() => {
            const a = {};
            const b = {a};
            a.b = b;
            return a;
        }''')
        self.assertIsNone(result)

    @sync
    async def test_accept_string(self):
        result = await self.page.evaluate('1 + 2')
        self.assertEqual(result, 3)

    @sync
    async def test_evaluate_force_expression(self):
        result = await self.page.evaluate(
            '() => null;\n1 + 2;', force_expr=True)
        self.assertEqual(result, 3)

    @sync
    async def test_accept_string_with_semicolon(self):
        result = await self.page.evaluate('1 + 5;')
        self.assertEqual(result, 6)

    @sync
    async def test_accept_string_with_comments(self):
        result = await self.page.evaluate('2 + 5;\n// do some math!')
        self.assertEqual(result, 7)

    @sync
    async def test_element_handle_as_argument(self):
        await self.page.setContent('<section>42</section>')
        element = await self.page.J('section')
        text = await self.page.evaluate('(e) => e.textContent', element)
        self.assertEqual(text, '42')

    @sync
    async def test_element_handle_disposed(self):
        await self.page.setContent('<section>39</section>')
        element = await self.page.J('section')
        self.assertTrue(element)
        await element.dispose()
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('(e) => e.textContent', element)
        self.assertIn('JSHandle is disposed', cm.exception.args[0])

    @sync
    async def test_element_handle_from_other_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        body = await self.page.frames[1].J('body')
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('body => body.innerHTML', body)
        self.assertIn(
            'JSHandles can be evaluated only in the context they were created',
            cm.exception.args[0],
        )

    @sync
    async def test_object_handle_as_argument(self):
        navigator = await self.page.evaluateHandle('() => navigator')
        self.assertTrue(navigator)
        text = await self.page.evaluate('(e) => e.userAgent', navigator)
        self.assertIn('Mozilla', text)

    @sync
    async def test_object_handle_to_primitive_value(self):
        aHandle = await self.page.evaluateHandle('() => 5')
        isFive = await self.page.evaluate('(e) => Object.is(e, 5)', aHandle)
        self.assertTrue(isFive)

    @sync
    async def test_simulate_user_gesture(self):
        playAudio = '''function playAudio() {
            const audio = document.createElement('audio');
            audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
            return audio.play();
        }'''  # noqa: E501
        await self.page.evaluate(playAudio)
        await self.page.evaluate('({})()'.format(playAudio), force_expr=True)

    @sync
    async def test_nice_error_after_navigation(self):
        executionContext = await self.page.mainFrame.executionContext()

        await asyncio.wait([
            self.page.waitForNavigation(),
            executionContext.evaluate('window.location.reload()'),
        ])

        with self.assertRaises(NetworkError) as cm:
            await executionContext.evaluate('() => null')
        self.assertIn('navigation', cm.exception.args[0])


class TestOfflineMode(BaseTestCase):
    @sync
    async def test_offline_mode(self):
        await self.page.setOfflineMode(True)
        with self.assertRaises(PageError):
            await self.page.goto(self.url)
        await self.page.setOfflineMode(False)
        res = await self.page.reload()
        self.assertEqual(res.status, 200)

    @sync
    async def test_emulate_navigator_offline(self):
        self.assertTrue(await self.page.evaluate('window.navigator.onLine'))
        await self.page.setOfflineMode(True)
        self.assertFalse(await self.page.evaluate('window.navigator.onLine'))
        await self.page.setOfflineMode(False)
        self.assertTrue(await self.page.evaluate('window.navigator.onLine'))


class TestEvaluateHandle(BaseTestCase):
    @sync
    async def test_evaluate_handle(self):
        windowHandle = await self.page.evaluateHandle('() => window')
        self.assertTrue(windowHandle)


class TestWaitFor(BaseTestCase):
    @sync
    async def test_wait_for_selector(self):
        fut = asyncio.ensure_future(self.page.waitFor('div'))
        fut.add_done_callback(lambda f: self.set_result(True))
        await self.page.goto(self.url + 'empty')
        self.assertFalse(self.result)
        await self.page.goto(self.url + 'static/grid.html')
        await fut
        self.assertTrue(self.result)

    @sync
    async def test_wait_for_xpath(self):
        waitFor = asyncio.ensure_future(self.page.waitFor('//div'))
        waitFor.add_done_callback(lambda fut: self.set_result(True))
        await self.page.goto(self.url + 'empty')
        self.assertFalse(self.result)
        await self.page.goto(self.url + 'static/grid.html')
        await waitFor
        self.assertTrue(self.result)

    @sync
    async def test_single_slash_fail(self):
        await self.page.setContent('<div>some text</div>')
        with self.assertRaises(Exception):
            await self.page.waitFor('/html/body/div')

    @sync
    async def test_wait_for_timeout(self):
        start_time = time.perf_counter()
        fut = asyncio.ensure_future(self.page.waitFor(100))
        fut.add_done_callback(lambda f: self.set_result(True))
        await fut
        self.assertGreater(time.perf_counter() - start_time, 0.1)
        self.assertTrue(self.result)

    @sync
    async def test_wait_for_error_type(self):
        with self.assertRaises(TypeError) as cm:
            await self.page.waitFor({'a': 1})
        self.assertIn('Unsupported target type', cm.exception.args[0])

    @sync
    async def test_wait_for_func_with_args(self):
        await self.page.waitFor('(arg1, arg2) => arg1 !== arg2', {}, 1, 2)


class TestConsole(BaseTestCase):
    @sync
    async def test_console_event(self):
        messages = []
        self.page.once('console', lambda m: messages.append(m))
        await self.page.evaluate('() => console.log("hello", 5, {foo: "bar"})')
        await asyncio.sleep(0.01)
        self.assertEqual(len(messages), 1)

        msg = messages[0]
        self.assertEqual(msg.type, 'log')
        self.assertEqual(msg.text, 'hello 5 JSHandle@object')
        self.assertEqual(await msg.args[0].jsonValue(), 'hello')
        self.assertEqual(await msg.args[1].jsonValue(), 5)
        self.assertEqual(await msg.args[2].jsonValue(), {'foo': 'bar'})

    @sync
    async def test_console_event_many(self):
        messages = []
        self.page.on('console', lambda m: messages.append(m))
        await self.page.evaluate('''
// A pair of time/timeEnd generates only one Console API call.
console.time('calling console.time');
console.timeEnd('calling console.time');
console.trace('calling console.trace');
console.dir('calling console.dir');
console.warn('calling console.warn');
console.error('calling console.error');
console.log(Promise.resolve('should not wait until resolved!'));
        ''')
        await asyncio.sleep(0.1)
        self.assertEqual(
            [msg.type for msg in messages],
            ['timeEnd', 'trace', 'dir', 'warning', 'error', 'log'],
        )
        self.assertIn('calling console.time', messages[0].text)
        self.assertEqual([msg.text for msg in messages[1:]], [
            'calling console.trace',
            'calling console.dir',
            'calling console.warn',
            'calling console.error',
            'JSHandle@promise',
        ])

    @sync
    async def test_console_window(self):
        messages = []
        self.page.once('console', lambda m: messages.append(m))
        await self.page.evaluate('console.error(window);')
        await asyncio.sleep(0.1)
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertEqual(msg.text, 'JSHandle@object')

    @sync
    async def test_trigger_correct_log(self):
        await self.page.goto('about:blank')
        messages = []
        self.page.on('console', lambda m: messages.append(m))
        asyncio.ensure_future(self.page.evaluate(
            'async url => fetch(url).catch(e => {})', self.url + 'empty'))
        await waitEvent(self.page, 'console')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertIn('No \'Access-Control-Allow-Origin\'', message.text)
        self.assertEqual(message.type, 'error')


class TestDOMContentLoaded(BaseTestCase):
    @sync
    async def test_fired(self):
        self.page.once('domcontentloaded', self.set_result(True))
        self.assertTrue(self.result)


class TestMetrics(BaseTestCase):
    def checkMetrics(self, metrics):
        metrics_to_check = {
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
        }
        for name, value in metrics.items():
            self.assertTrue(name in metrics_to_check)
            self.assertTrue(value >= 0)
            metrics_to_check.remove(name)
        self.assertEqual(len(metrics_to_check), 0)

    @sync
    async def test_metrics(self):
        await self.page.goto('about:blank')
        metrics = await self.page.metrics()
        self.checkMetrics(metrics)

    @sync
    async def test_metrics_event(self):
        fut = asyncio.get_event_loop().create_future()
        self.page.on('metrics', lambda metrics: fut.set_result(metrics))
        await self.page.evaluate('() => console.timeStamp("test42")')
        metrics = await fut
        self.assertEqual(metrics['title'], 'test42')
        self.checkMetrics(metrics['metrics'])


class TestGoto(BaseTestCase):
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
    async def test_response_when_page_changes_url(self):
        response = await self.page.goto(self.url + 'static/historyapi.html')
        self.assertTrue(response)
        self.assertEqual(response.status, 200)

    @sync
    async def test_goto_subframe_204(self):
        await self.page.goto(self.url + 'static/frame-204.html')

    @sync
    async def test_goto_fail_204(self):
        with self.assertRaises(PageError) as cm:
            await self.page.goto('http://httpstat.us/204')
        self.assertIn('net::ERR_ABORTED', cm.exception.args[0])

    @sync
    async def test_goto_documentloaded(self):
        import logging
        with self.assertLogs('pyppeteer', logging.WARNING):
            response = await self.page.goto(
                self.url + 'empty', waitUntil='documentloaded')
        self.assertEqual(response.status, 200)

    @sync
    async def test_goto_domcontentloaded(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='domcontentloaded')
        self.assertEqual(response.status, 200)

    @unittest.skip('This test should be fixed')
    @sync
    async def test_goto_history_api_beforeunload(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('''() => {
            window.addEventListener(
                'beforeunload',
                () => history.replaceState(null, 'initial', window.location.href),
                false,
            );
        }''')  # noqa: E501
        response = await self.page.goto(self.url + 'static/grid.html')
        self.assertTrue(response)
        self.assertEqual(response.status, 200)

    @sync
    async def test_goto_networkidle(self):
        with self.assertRaises(ValueError):
            await self.page.goto(self.url + 'empty', waitUntil='networkidle')

    @sync
    async def test_nav_networkidle0(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='networkidle0')
        self.assertEqual(response.status, 200)

    @sync
    async def test_nav_networkidle2(self):
        response = await self.page.goto(self.url + 'empty',
                                        waitUntil='networkidle2')
        self.assertEqual(response.status, 200)

    @sync
    async def test_goto_bad_url(self):
        with self.assertRaises(NetworkError):
            await self.page.goto('asdf')

    @sync
    async def test_goto_bad_resource(self):
        with self.assertRaises(PageError):
            await self.page.goto('http://localhost:44123/non-existing-url')

    @sync
    async def test_timeout(self):
        with self.assertRaises(TimeoutError):
            await self.page.goto(self.url + 'long', timeout=1)

    @sync
    async def test_timeout_default(self):
        self.page.setDefaultNavigationTimeout(1)
        with self.assertRaises(TimeoutError):
            await self.page.goto(self.url + 'long')

    @sync
    async def test_no_timeout(self):
        await self.page.goto(self.url + 'long', timeout=0)

    @sync
    async def test_valid_url(self):
        response = await self.page.goto(self.url + 'empty')
        self.assertEqual(response.status, 200)

    @sync
    async def test_data_url(self):
        response = await self.page.goto('data:text/html,hello')
        self.assertTrue(response.ok)

    @sync
    async def test_404(self):
        response = await self.page.goto(self.url + '/not-found')
        self.assertFalse(response.ok)
        self.assertEqual(response.status, 404)

    @sync
    async def test_redirect(self):
        response = await self.page.goto(self.url + 'redirect1')
        self.assertTrue(response.ok)
        self.assertEqual(response.url, self.url + 'redirect2')

    @unittest.skip('This test is not implemented')
    @sync
    async def test_wait_for_network_idle(self):
        pass

    @sync
    async def test_data_url_request(self):
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        dataURL = 'data:text/html,<div>yo</div>'
        response = await self.page.goto(dataURL)
        self.assertTrue(response.ok)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, dataURL)

    @sync
    async def test_url_with_hash(self):
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        response = await self.page.goto(self.url + 'empty#hash')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.url, self.url + 'empty')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, self.url + 'empty')

    @sync
    async def test_self_request_page(self):
        response = await self.page.goto(self.url + 'static/self-request.html')
        self.assertEqual(response.status, 200)
        self.assertIn('self-request.html', response.url)

    @sync
    async def test_show_url_in_error_message(self):
        dummy_port = 9000 if '9000' not in self.url else 9001
        url = 'http://localhost:{}/test/1.html'.format(dummy_port)
        with self.assertRaises(PageError) as cm:
            await self.page.goto(url)
        self.assertIn(url, cm.exception.args[0])


class TestWaitForNavigation(BaseTestCase):
    @sync
    async def test_wait_for_navigatoin(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.evaluate('(url) => window.location.href = url', self.url)
        )
        response = results[0]
        self.assertEqual(response.status, 200)
        self.assertEqual(response.url, self.url)

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_both_domcontentloaded_loaded(self):
        pass

    @sync
    async def test_click_anchor_link(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setContent('<a href="#foobar">foobar</a>')
        results = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.click('a'),
        )
        self.assertIsNone(results[0])
        self.assertEqual(self.page.url, self.url + 'empty#foobar')

    @sync
    async def test_return_nevigated_response_reload(self):
        await self.page.goto(self.url + 'empty')
        navPromise = asyncio.ensure_future(self.page.waitForNavigation())
        await self.page.reload()
        response = await navPromise
        self.assertEqual(response.url, self.url + 'empty')

    @sync
    async def test_history_push_state(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setContent('''
            <a onclick='javascript:pushState()'>SPA</a>
            <script>
                function pushState() { history.pushState({}, '', 'wow.html') }
            </script>
        ''')
        results = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.click('a'),
        )
        self.assertIsNone(results[0])
        self.assertEqual(self.page.url, self.url + 'wow.html')

    @sync
    async def test_history_replace_state(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setContent('''
            <a onclick='javascript:replaceState()'>SPA</a>
            <script>
                function replaceState() {
                    history.replaceState({}, '', 'replaced.html');
                }
            </script>
        ''')
        results = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.click('a'),
        )
        self.assertIsNone(results[0])
        self.assertEqual(self.page.url, self.url + 'replaced.html')

    @sync
    async def test_dom_history_back_forward(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setContent('''
            <a id="back" onclick='javascript:goBack()'>back</a>
            <a id="forward" onclick='javascript:goForward()'>forward</a>
            <script>
                function goBack() { history.back(); }
                function goForward() { history.forward(); }
                history.pushState({}, '', '/first.html');
                history.pushState({}, '', '/second.html');
            </script>
        ''')
        self.assertEqual(self.page.url, self.url + 'second.html')
        results_back = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.click('a#back'),
        )
        self.assertIsNone(results_back[0])
        self.assertEqual(self.page.url, self.url + 'first.html')

        results_forward = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.click('a#forward'),
        )
        self.assertIsNone(results_forward[0])
        self.assertEqual(self.page.url, self.url + 'second.html')

    @sync
    async def test_subframe_issues(self):
        navigationPromise = asyncio.ensure_future(
            self.page.goto(self.url + 'static/one-frame.html'))
        frame = await waitEvent(self.page, 'frameattached')
        fut = asyncio.get_event_loop().create_future()

        def is_same_frame(f):
            if f == frame:
                fut.set_result(True)

        self.page.on('framenavigated', is_same_frame)
        asyncio.ensure_future(frame.evaluate('window.stop()'))
        await navigationPromise


class TestWaitForRequest(BaseTestCase):
    @sync
    async def test_wait_for_request(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForRequest(self.url + 'static/digits/2.png'),
            self.page.evaluate('''() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }''')
        )
        request = results[0]
        self.assertEqual(request.url, self.url + 'static/digits/2.png')

    @sync
    async def test_predicate(self):
        await self.page.goto(self.url + 'empty')

        def predicate(req):
            return req.url == self.url + 'static/digits/2.png'

        results = await asyncio.gather(
            self.page.waitForRequest(predicate),
            self.page.evaluate('''() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }''')
        )
        request = results[0]
        self.assertEqual(request.url, self.url + 'static/digits/2.png')

    @sync
    async def test_no_timeout(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForRequest(
                self.url + 'static/digits/2.png',
                timeout=0,
            ),
            self.page.evaluate('''() => setTimeout(() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }, 50)''')
        )
        request = results[0]
        self.assertEqual(request.url, self.url + 'static/digits/2.png')


class TestWaitForResponse(BaseTestCase):
    @sync
    async def test_wait_for_response(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForResponse(self.url + 'static/digits/2.png'),
            self.page.evaluate('''() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }''')
        )
        response = results[0]
        self.assertEqual(response.url, self.url + 'static/digits/2.png')

    @sync
    async def test_predicate(self):
        await self.page.goto(self.url + 'empty')

        def predicate(response):
            return response.url == self.url + 'static/digits/2.png'

        results = await asyncio.gather(
            self.page.waitForResponse(predicate),
            self.page.evaluate('''() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }''')
        )
        response = results[0]
        self.assertEqual(response.url, self.url + 'static/digits/2.png')

    @sync
    async def test_no_timeout(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForResponse(
                self.url + 'static/digits/2.png',
                timeout=0,
            ),
            self.page.evaluate('''() => setTimeout(() => {
                fetch('/static/digits/1.png');
                fetch('/static/digits/2.png');
                fetch('/static/digits/3.png');
            }, 50)''')
        )
        response = results[0]
        self.assertEqual(response.url, self.url + 'static/digits/2.png')


class TestGoBack(BaseTestCase):
    @sync
    async def test_back(self):
        await self.page.goto(self.url + 'empty')
        await self.page.goto(self.url + 'static/textarea.html')

        response = await self.page.goBack()
        self.assertTrue(response.ok)
        self.assertIn('empty', response.url)

        response = await self.page.goForward()
        self.assertTrue(response.ok)
        self.assertIn('static/textarea.html', response.url)

        response = await self.page.goForward()
        self.assertIsNone(response)

    @sync
    async def test_history_api(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('''() => {
            history.pushState({}, '', '/first.html');
            history.pushState({}, '', '/second.html');
        }''')
        self.assertEqual(self.page.url, self.url + 'second.html')

        await self.page.goBack()
        self.assertEqual(self.page.url, self.url + 'first.html')
        await self.page.goBack()
        self.assertEqual(self.page.url, self.url + 'empty')
        await self.page.goForward()
        self.assertEqual(self.page.url, self.url + 'first.html')


class TestExposeFunction(BaseTestCase):
    @sync
    async def test_expose_function(self):
        await self.page.goto(self.url + 'empty')
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        result = await self.page.evaluate('(a, b) => compute(a, b)', 9, 4)
        self.assertEqual(result, 36)

    @sync
    async def test_call_from_evaluate_on_document(self):
        await self.page.goto(self.url + 'empty')
        called = list()

        def woof():
            called.append(True)

        await self.page.exposeFunction('woof', woof)
        await self.page.evaluateOnNewDocument('() => woof()')
        await self.page.reload()
        self.assertTrue(called)

    @sync
    async def test_expose_function_other_page(self):
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        await self.page.goto(self.url + 'empty')
        result = await self.page.evaluate('(a, b) => compute(a, b)', 9, 4)
        self.assertEqual(result, 36)

    @unittest.skip('Python does not support promise in expose function')
    @sync
    async def test_expose_function_return_promise(self):
        async def compute(a, b):
            return a * b

        await self.page.exposeFunction('compute', compute)
        result = await self.page.evaluate('() => compute(3, 5)')
        self.assertEqual(result, 15)

    @sync
    async def test_expose_function_frames(self):
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        await self.page.goto(self.url + 'static/nested-frames.html')
        frame = self.page.frames[1]
        result = await frame.evaluate('() => compute(3, 5)')
        self.assertEqual(result, 15)

    @sync
    async def test_expose_function_frames_before_navigation(self):
        await self.page.goto(self.url + 'static/nested-frames.html')
        await self.page.exposeFunction('compute', lambda a, b: a * b)
        frame = self.page.frames[1]
        result = await frame.evaluate('() => compute(3, 5)')
        self.assertEqual(result, 15)


class TestErrorPage(BaseTestCase):
    @sync
    async def test_error_page(self):
        error = None

        def check(e):
            nonlocal error
            error = e

        self.page.on('pageerror', check)
        await self.page.goto(self.url + 'static/error.html')
        self.assertIsNotNone(error)
        self.assertIn('Fancy', error.args[0])


class TestRequest(BaseTestCase):
    @sync
    async def test_request(self):
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, self.url + 'empty')
        self.assertEqual(requests[0].frame, self.page.mainFrame)
        self.assertEqual(requests[0].frame.url, self.url + 'empty')
        self.assertEqual(requests[1].url, self.url + 'empty')
        self.assertEqual(requests[1].frame, self.page.frames[1])
        self.assertEqual(requests[1].frame.url, self.url + 'empty')


class TestQuerySelector(BaseTestCase):
    @sync
    async def test_jeval(self):
        await self.page.setContent(
            '<section id="testAttribute">43543</section>')
        idAttribute = await self.page.Jeval('section', 'e => e.id')
        self.assertEqual(idAttribute, 'testAttribute')

    @sync
    async def test_jeval_argument(self):
        await self.page.setContent('<section>hello</section>')
        text = await self.page.Jeval(
            'section', '(e, suffix) => e.textContent + suffix', ' world!')
        self.assertEqual(text, 'hello world!')

    @sync
    async def test_jeval_argument_element(self):
        await self.page.setContent('<section>hello</section><div> world</div>')
        divHandle = await self.page.J('div')
        text = await self.page.Jeval(
            'section',
            '(e, div) => e.textContent + div.textContent',
            divHandle,
        )
        self.assertEqual(text, 'hello world')

    @sync
    async def test_jeval_not_found(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.Jeval('section', 'e => e.id')
        self.assertIn(
            'failed to find element matching selector "section"',
            cm.exception.args[0],
        )

    @sync
    async def test_JJeval(self):
        await self.page.setContent(
            '<div>hello</div><div>beautiful</div><div>world</div>')
        divsCount = await self.page.JJeval('div', 'divs => divs.length')
        self.assertEqual(divsCount, 3)

    @sync
    async def test_query_selector(self):
        await self.page.setContent('<section>test</section>')
        element = await self.page.J('section')
        self.assertTrue(element)

    @unittest.skipIf(sys.version_info < (3, 6), 'Elements order is unstable')
    @sync
    async def test_query_selector_all(self):
        await self.page.setContent('<div>A</div><br/><div>B</div>')
        elements = await self.page.JJ('div')
        self.assertEqual(len(elements), 2)
        results = []
        for e in elements:
            results.append(await self.page.evaluate('e => e.textContent', e))
        self.assertEqual(results, ['A', 'B'])

    @sync
    async def test_query_selector_all_not_found(self):
        await self.page.goto(self.url + 'empty')
        elements = await self.page.JJ('div')
        self.assertEqual(len(elements), 0)

    @sync
    async def test_xpath(self):
        await self.page.setContent('<section>test</section>')
        element = await self.page.xpath('/html/body/section')
        self.assertTrue(element)

    @sync
    async def test_xpath_alias(self):
        await self.page.setContent('<section>test</section>')
        element = await self.page.Jx('/html/body/section')
        self.assertTrue(element)

    @sync
    async def test_xpath_not_found(self):
        element = await self.page.xpath('/html/body/no-such-tag')
        self.assertEqual(element, [])

    @sync
    async def test_xpath_multiple(self):
        await self.page.setContent('<div></div><div></div>')
        element = await self.page.xpath('/html/body/div')
        self.assertEqual(len(element), 2)


class TestUserAgent(BaseTestCase):
    @sync
    async def test_user_agent(self):
        self.assertIn('Mozilla', await self.page.evaluate(
            '() => navigator.userAgent'))
        await self.page.setUserAgent('foobar')
        await self.page.goto(self.url)
        self.assertEqual('foobar', await self.page.evaluate(
            '() => navigator.userAgent'))

    @sync
    async def test_user_agent_mobile_emulate(self):
        await self.page.goto(self.url + 'static/mobile.html')
        self.assertIn(
            'Chrome', await self.page.evaluate('navigator.userAgent'))
        await self.page.setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1')  # noqa: E501
        self.assertIn(
            'Safari', await self.page.evaluate('navigator.userAgent'))


class TestExtraHTTPHeader(BaseTestCase):
    @sync
    async def test_extra_http_header(self):
        await self.page.setExtraHTTPHeaders({'foo': 'bar'})

        from tornado.web import RequestHandler
        requests = []

        class HeaderFetcher(RequestHandler):
            def get(self):
                requests.append(self.request)
                self.write('')

        self.app.add_handlers('localhost', [('/header', HeaderFetcher)])
        await self.page.goto(self.url + 'header')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].headers['foo'], 'bar')

    @sync
    async def test_non_string_value(self):
        with self.assertRaises(TypeError) as e:
            await self.page.setExtraHTTPHeaders({'foo': 1})
        self.assertIn(
            'Expected value of header "foo" to be string', e.exception.args[0])


class TestAuthenticate(BaseTestCase):
    @sync
    async def test_auth(self):
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 401)
        await self.page.authenticate({'username': 'user', 'password': 'pass'})
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 200)


class TestAuthenticateFailed(BaseTestCase):
    @sync
    async def test_auth_fail(self):
        await self.page.authenticate({'username': 'foo', 'password': 'bar'})
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 401)


class TestAuthenticateDisable(BaseTestCase):
    @sync
    async def test_disable_auth(self):
        await self.page.authenticate({'username': 'user', 'password': 'pass'})
        response = await self.page.goto(self.url + 'auth')
        self.assertEqual(response.status, 200)
        await self.page.authenticate(None)
        response = await self.page.goto(
            'http://127.0.0.1:{}/auth'.format(self.port))
        self.assertEqual(response.status, 401)


class TestSetContent(BaseTestCase):
    expectedOutput = '<html><head></head><body><div>hello</div></body></html>'

    @sync
    async def test_set_content(self):
        await self.page.setContent('<div>hello</div>')
        result = await self.page.content()
        self.assertEqual(result, self.expectedOutput)

    @sync
    async def test_with_doctype(self):
        doctype = '<!DOCTYPE html>'
        await self.page.setContent(doctype + '<div>hello</div>')
        result = await self.page.content()
        self.assertEqual(result, doctype + self.expectedOutput)

    @sync
    async def test_with_html4_doctype(self):
        doctype = ('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                   '"http://www.w3.org/TR/html4/strict.dtd">')
        await self.page.setContent(doctype + '<div>hello</div>')
        result = await self.page.content()
        self.assertEqual(result, doctype + self.expectedOutput)


class TestSetBypassCSP(BaseTestCase):
    @sync
    async def test_bypass_csp_meta_tag(self):
        await self.page.goto(self.url + 'static/csp.html')
        with self.assertRaises(ElementHandleError):
            await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertIsNone(await self.page.evaluate('window.__injected'))

        await self.page.setBypassCSP(True)
        await self.page.reload()
        await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertEqual(await self.page.evaluate('window.__injected'), 42)

    @sync
    async def test_bypass_csp_header(self):
        await self.page.goto(self.url + 'csp')
        with self.assertRaises(ElementHandleError):
            await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertIsNone(await self.page.evaluate('window.__injected'))

        await self.page.setBypassCSP(True)
        await self.page.reload()
        await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertEqual(await self.page.evaluate('window.__injected'), 42)

    @sync
    async def test_bypass_scp_cross_process(self):
        await self.page.setBypassCSP(True)
        await self.page.goto(self.url + 'static/csp.html')
        await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertEqual(await self.page.evaluate('window.__injected'), 42)

        await self.page.goto(
            'http://127.0.0.1:{}/static/csp.html'.format(self.port))
        await self.page.addScriptTag(content='window.__injected = 42;')
        self.assertEqual(await self.page.evaluate('window.__injected'), 42)


class TestAddScriptTag(BaseTestCase):
    @sync
    async def test_script_tag_error(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(ValueError):
            await self.page.addScriptTag('/static/injectedfile.js')

    @sync
    async def test_script_tag_url(self):
        await self.page.goto(self.url + 'empty')
        scriptHandle = await self.page.addScriptTag(
            url='/static/injectedfile.js')
        self.assertIsNotNone(scriptHandle.asElement())
        self.assertEqual(await self.page.evaluate('__injected'), 42)

    @sync
    async def test_script_tag_url_fail(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(PageError) as cm:
            await self.page.addScriptTag({'url': '/nonexistsfile.js'})
        self.assertEqual(cm.exception.args[0],
                         'Loading script from /nonexistsfile.js failed')

    @sync
    async def test_script_tag_path(self):
        curdir = Path(__file__).parent
        path = str(curdir / 'static' / 'injectedfile.js')
        await self.page.goto(self.url + 'empty')
        scriptHanlde = await self.page.addScriptTag(path=path)
        self.assertIsNotNone(scriptHanlde.asElement())
        self.assertEqual(await self.page.evaluate('__injected'), 42)

    @sync
    async def test_script_tag_path_source_map(self):
        curdir = Path(__file__).parent
        path = str(curdir / 'static' / 'injectedfile.js')
        await self.page.goto(self.url + 'empty')
        await self.page.addScriptTag(path=path)
        result = await self.page.evaluate('__injectedError.stack')
        self.assertIn(str(Path('static') / 'injectedfile.js'), result)

    @sync
    async def test_script_tag_content(self):
        await self.page.goto(self.url + 'empty')
        scriptHandle = await self.page.addScriptTag(
            content='window.__injected = 35;')
        self.assertIsNotNone(scriptHandle.asElement())
        self.assertEqual(await self.page.evaluate('__injected'), 35)

    @sync
    async def test_scp_error_content(self):
        await self.page.goto(self.url + 'static/csp.html')
        with self.assertRaises(ElementHandleError):
            await self.page.addScriptTag(content='window.__injected = 35;')

    @sync
    async def test_scp_error_url(self):
        await self.page.goto(self.url + 'static/csp.html')
        with self.assertRaises(PageError):
            await self.page.addScriptTag(
                url='http://127.0.0.1:{}/static/injectedfile.js'.format(self.port)  # noqa: E501
            )

    @sync
    async def test_module_url(self):
        await self.page.goto(self.url + 'empty')
        await self.page.addScriptTag(
            url='/static/es6/es6import.js', type='module')
        self.assertEqual(await self.page.evaluate('__es6injected'), 42)

    @sync
    async def test_module_path(self):
        await self.page.goto(self.url + 'empty')
        curdir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(curdir, 'static', 'es6', 'es6pathimport.js')
        await self.page.addScriptTag(path=path, type='module')
        await self.page.waitForFunction('window.__es6injected')
        self.assertEqual(await self.page.evaluate('__es6injected'), 42)

    @sync
    async def test_module_content(self):
        await self.page.goto(self.url + 'empty')
        content = '''
            import num from '/static/es6/es6module.js';
            window.__es6injected = num;
        '''
        await self.page.addScriptTag(content=content, type='module')
        await self.page.waitForFunction('window.__es6injected')
        self.assertEqual(await self.page.evaluate('__es6injected'), 42)


class TestAddStyleTag(BaseTestCase):
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
    async def test_style_tag_url_fail(self):
        await self.page.goto(self.url + 'empty')
        with self.assertRaises(PageError) as cm:
            await self.page.addStyleTag(url='/nonexistfile.css')
        self.assertEqual(cm.exception.args[0],
                         'Loading style from /nonexistfile.css failed')

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
    async def test_style_tag_path_source_map(self):
        curdir = Path(__file__).parent
        path = str(curdir / 'static' / 'injectedstyle.css')
        await self.page.goto(self.url + 'empty')
        await self.page.addStyleTag(path=str(path))
        styleHandle = await self.page.J('style')
        styleContent = await self.page.evaluate(
            'style => style.innerHTML', styleHandle)
        self.assertIn(str(Path('static') / 'injectedstyle.css'), styleContent)

    @sync
    async def test_style_tag_content(self):
        await self.page.goto(self.url + 'empty')
        self.assertEqual(await self.get_bgcolor(), 'rgba(0, 0, 0, 0)')
        styleHandle = await self.page.addStyleTag(content=' body {background-color: green;}')  # noqa: E501
        self.assertIsNotNone(styleHandle.asElement())
        self.assertEqual(await self.get_bgcolor(), 'rgb(0, 128, 0)')

    @sync
    async def test_csp_error_content(self):
        await self.page.goto(self.url + 'static/csp.html')
        with self.assertRaises(ElementHandleError):
            await self.page.addStyleTag(
                content='body { background-color: green; }')

    @sync
    async def test_csp_error_url(self):
        await self.page.goto(self.url + 'static/csp.html')
        with self.assertRaises(PageError):
            await self.page.addStyleTag(
                url='http://127.0.0.1:{}/static/injectedstyle.css'.format(self.port)  # noqa: E501
            )


class TestUrl(BaseTestCase):
    @sync
    async def test_url(self):
        await self.page.goto('about:blank')
        self.assertEqual(self.page.url, 'about:blank')
        await self.page.goto(self.url + 'empty')
        self.assertEqual(self.page.url, self.url + 'empty')


class TestViewport(BaseTestCase):
    iPhoneViewport = iPhone['viewport']

    @sync
    async def test_viewport(self):
        self.assertEqual(self.page.viewport, {'width': 800, 'height': 600})
        await self.page.setViewport({'width': 123, 'height': 456})
        self.assertEqual(self.page.viewport, {'width': 123, 'height': 456})

    @sync
    async def test_mobile_emulation(self):
        await self.page.goto(self.url + 'static/mobile.html')
        self.assertEqual(await self.page.evaluate('window.innerWidth'), 800)
        await self.page.setViewport(self.iPhoneViewport)
        self.assertEqual(await self.page.evaluate('window.innerWidth'), 375)
        await self.page.setViewport({'width': 400, 'height': 300})
        self.assertEqual(await self.page.evaluate('window.innerWidth'), 400)

    @sync
    async def test_touch_emulation(self):
        await self.page.goto(self.url + 'static/mobile.html')
        self.assertFalse(await self.page.evaluate('"ontouchstart" in window'))
        await self.page.setViewport(self.iPhoneViewport)
        self.assertTrue(await self.page.evaluate('"ontouchstart" in window'))

        dispatchTouch = '''() => {
            let fulfill;
            const promise = new Promise(x => fulfill = x);
            window.ontouchstart = function(e) {
                fulfill('Received touch');
            };
            window.dispatchEvent(new Event('touchstart'));

            fulfill('Did not receive touch');

            return promise;
        }'''
        self.assertEqual(
            await self.page.evaluate(dispatchTouch), 'Received touch')

        await self.page.setViewport({'width': 100, 'height': 100})
        self.assertFalse(await self.page.evaluate('"ontouchstart" in window'))

    @sync
    async def test_detect_by_modernizr(self):
        await self.page.goto(self.url + 'static/detect-touch.html')
        self.assertEqual(
            await self.page.evaluate('document.body.textContent.trim()'),
            'NO'
        )
        await self.page.setViewport(self.iPhoneViewport)
        self.assertEqual(
            await self.page.evaluate('document.body.textContent.trim()'),
            'YES'
        )

    @sync
    async def test_detect_touch_viewport_touch(self):
        await self.page.setViewport({'width': 800, 'height': 600, 'hasTouch': True})  # noqa: E501
        await self.page.addScriptTag({'url': self.url + 'static/modernizr.js'})
        self.assertTrue(await self.page.evaluate('() => Modernizr.touchevents'))  # noqa: E501

    @sync
    async def test_landscape_emulation(self):
        await self.page.goto(self.url + 'static/mobile.html')
        self.assertEqual(
            await self.page.evaluate('screen.orientation.type'),
            'portrait-primary',
        )
        iPhoneLandscapeViewport = self.iPhoneViewport.copy()
        iPhoneLandscapeViewport['isLandscape'] = True
        await self.page.setViewport(iPhoneLandscapeViewport)
        self.assertEqual(
            await self.page.evaluate('screen.orientation.type'),
            'landscape-primary',
        )
        await self.page.setViewport({'width': 100, 'height': 100})
        self.assertEqual(
            await self.page.evaluate('screen.orientation.type'),
            'portrait-primary',
        )


class TestEmulate(BaseTestCase):
    @sync
    async def test_emulate(self):
        await self.page.goto(self.url + 'static/mobile.html')
        await self.page.emulate(iPhone)
        self.assertEqual(await self.page.evaluate('window.innerWidth'), 375)
        self.assertIn(
            'Safari', await self.page.evaluate('navigator.userAgent'))

    @sync
    async def test_click(self):
        await self.page.emulate(iPhone)
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate(
            'button => button.style.marginTop = "200px"', button)
        await button.click()
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')


class TestEmulateMedia(BaseTestCase):
    @sync
    async def test_emulate_media(self):
        self.assertTrue(
            await self.page.evaluate('matchMedia("screen").matches'))
        self.assertFalse(
            await self.page.evaluate('matchMedia("print").matches'))
        await self.page.emulateMedia('print')
        self.assertFalse(
            await self.page.evaluate('matchMedia("screen").matches'))
        self.assertTrue(
            await self.page.evaluate('matchMedia("print").matches'))
        await self.page.emulateMedia(None)
        self.assertTrue(
            await self.page.evaluate('matchMedia("screen").matches'))
        self.assertFalse(
            await self.page.evaluate('matchMedia("print").matches'))

    @sync
    async def test_emulate_media_bad_arg(self):
        with self.assertRaises(ValueError) as cm:
            await self.page.emulateMedia('bad')
        self.assertEqual(cm.exception.args[0], 'Unsupported media type: bad')


class TestJavaScriptEnabled(BaseTestCase):
    @sync
    async def test_set_javascript_enabled(self):
        await self.page.setJavaScriptEnabled(False)
        await self.page.goto(
            'data:text/html, <script>var something = "forbidden"</script>')
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('something')
        self.assertIn('something is not defined', cm.exception.args[0])

        await self.page.setJavaScriptEnabled(True)
        await self.page.goto(
            'data:text/html, <script>var something = "forbidden"</script>')
        self.assertEqual(await self.page.evaluate('something'), 'forbidden')


class TestEvaluateOnNewDocument(BaseTestCase):
    @sync
    async def test_evaluate_before_else_on_page(self):
        await self.page.evaluateOnNewDocument('() => window.injected = 123')
        await self.page.goto(self.url + 'static/temperable.html')
        self.assertEqual(await self.page.evaluate('window.result'), 123)

    @sync
    async def test_csp(self):
        await self.page.evaluateOnNewDocument('() => window.injected = 123')
        await self.page.goto(self.url + 'csp')
        self.assertEqual(await self.page.evaluate('window.injected'), 123)
        with self.assertRaises(ElementHandleError):
            await self.page.addScriptTag(content='window.e = 10;')
        self.assertIsNone(await self.page.evaluate('window.e'))


class TestCacheEnabled(BaseTestCase):
    @sync
    async def test_cache_enable_disable(self):
        responses = {}

        def set_response(res):
            responses[res.url.split('/').pop()] = res

        self.page.on('response', set_response)
        await self.page.goto(self.url + 'static/cached/one-style.html',
                             waitUntil='networkidle2')
        await self.page.reload(waitUntil='networkidle2')
        self.assertTrue(responses.get('one-style.css').fromCache)

        await self.page.setCacheEnabled(False)
        await self.page.reload(waitUntil='networkidle2')
        self.assertFalse(responses.get('one-style.css').fromCache)


class TestPDF(BaseTestCase):
    @sync
    async def test_pdf(self):
        outfile = Path(__file__).parent / 'output.pdf'
        await self.page.pdf({'path': str(outfile)})
        self.assertTrue(outfile.is_file())
        with outfile.open('rb') as f:
            pdf = f.read()
        self.assertGreater(len(pdf), 0)
        outfile.unlink()


class TestTitle(BaseTestCase):
    @sync
    async def test_title(self):
        await self.page.goto(self.url + 'static/button.html')
        self.assertEqual(await self.page.title(), 'Button test')


class TestSelect(BaseTestCase):
    def setUp(self):
        super().setUp()
        sync(self.page.goto(self.url + 'static/select.html'))

    @sync
    async def test_select(self):
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
    async def test_select_first_item(self):
        await self.page.select('select', 'blue', 'green', 'red')
        self.assertEqual(await self.page.evaluate('result.onInput'), ['blue'])
        self.assertEqual(await self.page.evaluate('result.onChange'), ['blue'])

    @sync
    async def test_select_multiple(self):
        await self.page.evaluate('makeMultiple();')
        values = await self.page.select('select', 'blue', 'green', 'red')
        self.assertEqual(values, ['blue', 'green', 'red'])
        _input = await self.page.evaluate('result.onInput')
        self.assertEqual(_input, ['blue', 'green', 'red'])
        change = await self.page.evaluate('result.onChange')
        self.assertEqual(change, ['blue', 'green', 'red'])

    @sync
    async def test_select_not_select_element(self):
        with self.assertRaises(ElementHandleError):
            await self.page.select('body', '')

    @sync
    async def test_select_no_match(self):
        values = await self.page.select('select', 'abc', 'def')
        self.assertEqual(values, [])

    @sync
    async def test_return_selected_elements(self):
        await self.page.evaluate('makeMultiple()')
        result = await self.page.select('select', 'blue', 'black', 'magenta')
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result), {'blue', 'black', 'magenta'})

    @sync
    async def test_select_not_multiple(self):
        values = await self.page.select('select', 'blue', 'green', 'red')
        self.assertEqual(len(values), 1)

    @sync
    async def test_select_no_value(self):
        values = await self.page.select('select')
        self.assertEqual(values, [])

    @sync
    async def test_select_deselect(self):
        await self.page.select('select', 'blue', 'green', 'red')
        await self.page.select('select')
        result = await self.page.Jeval(
            'select',
            'elm => Array.from(elm.options).every(option => !option.selected)'
        )
        self.assertTrue(result)

    @sync
    async def test_select_deselect_multiple(self):
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
        with self.assertRaises(TypeError):
            await self.page.select('select', 12)


class TestCookie(BaseTestCase):
    @sync
    async def test_cookies(self):
        await self.page.goto(self.url)
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
        self.assertIn(cookies, [
            [
                {
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
                }
            ],
            [
                {
                    'name': 'username',
                    'value': 'John Doe',
                    'domain': 'localhost',
                    'path': '/',
                    'expires': -1,
                    'size': 16,
                    'httpOnly': False,
                    'secure': False,
                    'session': True,
                }, {
                    'name': 'password',
                    'value': '123456',
                    'domain': 'localhost',
                    'path': '/',
                    'expires': -1,
                    'size': 14,
                    'httpOnly': False,
                    'secure': False,
                    'session': True,
                }
            ]
        ])
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


class TestCookieWithPath(BaseTestCase):
    @sync
    async def test_set_cookie_with_path(self):
        await self.page.goto(self.url + 'static/grid.html')
        await self.page.setCookie({
            'name': 'gridcookie',
            'value': 'GRID',
            'path': '/static/grid.html',
        })
        self.assertEqual(await self.page.cookies(), [{
            'name': 'gridcookie',
            'value': 'GRID',
            'path': '/static/grid.html',
            'domain': 'localhost',
            'expires': -1,
            'size': 14,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])


class TestCookieDelete(BaseTestCase):
    @sync
    async def test_delete_cookie(self):
        await self.page.goto(self.url)
        await self.page.setCookie({
            'name': 'cookie1',
            'value': '1',
        }, {
            'name': 'cookie2',
            'value': '2',
        }, {
            'name': 'cookie3',
            'value': '3',
        })
        self.assertEqual(
            await self.page.evaluate('document.cookie'),
            'cookie1=1; cookie2=2; cookie3=3'
        )
        await self.page.deleteCookie({'name': 'cookie2'})
        self.assertEqual(
            await self.page.evaluate('document.cookie'),
            'cookie1=1; cookie3=3'
        )


class TestCookieDomain(BaseTestCase):
    @sync
    async def test_different_domain(self):
        await self.page.goto(self.url + 'static/grid.html')
        await self.page.setCookie({
            'name': 'example-cookie',
            'value': 'best',
            'url': 'https://www.example.com',
        })
        self.assertEqual(await self.page.evaluate('document.cookie'), '')
        self.assertEqual(await self.page.cookies(), [])
        self.assertEqual(await self.page.cookies('https://www.example.com'), [{
            'name': 'example-cookie',
            'value': 'best',
            'domain': 'www.example.com',
            'path': '/',
            'expires': -1,
            'size': 18,
            'httpOnly': False,
            'secure': True,
            'session': True,
        }])


class TestCookieFrames(BaseTestCase):
    @sync
    async def test_frame(self):
        await self.page.goto(self.url + 'static/grid.html')
        await self.page.setCookie({
            'name': 'localhost-cookie',
            'value': 'best',
        })
        url_127 = 'http://127.0.0.1:{}'.format(self.port)
        await self.page.evaluate('''src => {
            let fulfill;
            const promise = new Promise(x => fulfill = x);
            const iframe = document.createElement('iframe');
            document.body.appendChild(iframe);
            iframe.onload = fulfill;
            iframe.src = src;
            return promise;
        }''', url_127)
        await self.page.setCookie({
            'name': '127-cookie',
            'value': 'worst',
            'url': url_127,
        })

        self.assertEqual(
            await self.page.evaluate('document.cookie'),
            'localhost-cookie=best',
        )
        self.assertEqual(
            await self.page.frames[1].evaluate('document.cookie'),
            '127-cookie=worst',
        )

        self.assertEqual(await self.page.cookies(), [{
            'name': 'localhost-cookie',
            'value': 'best',
            'domain': 'localhost',
            'path': '/',
            'expires': -1,
            'size': 20,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])
        self.assertEqual(await self.page.cookies(url_127), [{
            'name': '127-cookie',
            'value': 'worst',
            'domain': '127.0.0.1',
            'path': '/',
            'expires': -1,
            'size': 15,
            'httpOnly': False,
            'secure': False,
            'session': True,
        }])


class TestEvents(BaseTestCase):
    @sync
    async def test_close_window_close(self):
        loop = asyncio.get_event_loop()
        newPagePromise = loop.create_future()

        async def page_created(target):
            page = await target.page()
            newPagePromise.set_result(page)

        self.context.once(
            'targetcreated',
            lambda target: loop.create_task(page_created(target)),
        )
        await self.page.evaluate(
            'window["newPage"] = window.open("about:blank")')
        newPage = await newPagePromise

        closedPromise = loop.create_future()
        newPage.on('close', lambda: closedPromise.set_result(True))
        await self.page.evaluate('window["newPage"].close()')
        await closedPromise

    @sync
    async def test_close_page_close(self):
        newPage = await self.context.newPage()
        closedPromise = asyncio.get_event_loop().create_future()
        newPage.on('close', lambda: closedPromise.set_result(True))
        await newPage.close()
        await closedPromise


class TestBrowser(BaseTestCase):
    @sync
    async def test_get_browser(self):
        self.assertIs(self.page.browser, self.browser)
