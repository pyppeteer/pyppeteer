#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import math
import time
import unittest

from syncer import sync

from pyppeteer.errors import ElementHandleError, NetworkError, PageError
from pyppeteer.errors import TimeoutError

from base import BaseTestCase
from frame_utils import attachFrame


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

    @unittest.skip('Cannot pass this test')
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
    async def test_paromise_reject(self):
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('() => not.existing.object.property')
        self.assertIn('not is not defined', cm.exception.args[0])

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

    @unittest.skip('Cannot pass this  test')
    @sync
    async def test_serialize_null_field(self):
        result = await self.page.evaluate('() => {a: undefined}')
        self.assertEqual(result, {})

    @unittest.skip('Cannot pass this  test')
    @sync
    async def test_fail_window_object(self):
        result = await self.page.evaluate('() => window')
        self.assertIsNone(result)

    @sync
    async def test_accept_string(self):
        result = await self.page.evaluate('1 + 2')
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


class TestOfflineMode(BaseTestCase):
    @sync
    async def test_offline_mode(self):
        await self.page.setOfflineMode(True)
        with self.assertRaises(PageError):
            await self.page.goto(self.url)
        await self.page.setOfflineMode(False)
        res = await self.page.reload()
        self.assertEqual(res.status, 304)

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
    def setUp(self):
        super().setUp()
        sync(self.page.goto(self.url + 'empty'))
        self.result = False

    def set_result(self, value):
        self.result = value

    @sync
    async def test_wait_for_page_navigated(self):
        fut = asyncio.ensure_future(self.page.waitFor('h1'))
        fut.add_done_callback(lambda f: self.set_result(True))
        await self.page.goto(self.url + 'empty')
        self.assertFalse(self.result)
        await self.page.goto(self.url)
        await fut
        self.assertTrue(self.result)

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
    def setUp(self):
        super().setUp()
        sync(self.page.goto(self.url + 'empty'))

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


class TestMetrics(BaseTestCase):
    def checkMetrics(self, metrics):
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
        self.assertIn(response.status, [200, 304])

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
        self.assertIn(response.status, [200, 304])
        self.assertEqual(response.url, self.url + 'empty')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, self.url + 'empty')
