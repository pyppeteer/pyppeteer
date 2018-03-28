#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import math
from pathlib import Path
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


class TestWaitForNavigation(BaseTestCase):
    @sync
    async def test_wait_for_navigatoin(self):
        await self.page.goto(self.url + 'empty')
        results = await asyncio.gather(
            self.page.waitForNavigation(),
            self.page.evaluate('(url) => window.location.href = url', self.url)
        )
        response = results[0]
        self.assertIn(response.status, [200, 304])
        self.assertEqual(response.url, self.url)

    @unittest.skip('This test is not implemented')
    @sync
    async def test_both_documentloaded_loaded(self):
        pass


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


class TestExposeFunctoin(BaseTestCase):
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

    @unittest.skip('Python does not support promise in expose function')
    @sync
    async def test_expose_function_return_promise(self):
        async def compute(a, b):
            return a * b

        await self.page.exposeFunction('compute', compute)
        result = await self.page.evaluate('() => compute(3, 5)')
        print(result)
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


class TestRequestInterception(BaseTestCase):
    @sync
    async def test_request_interception(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            self.assertIn('empty', req.url)
            self.assertTrue(req.headers.get('user-agent'))
            self.assertEqual(req.method, 'GET')
            self.assertIsNone(req.postData)
            self.assertEqual(req.resourceType, 'document')
            self.assertEqual(req.frame, self.page.mainFrame)
            self.assertEqual(req.frame.url, self.url)
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

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_request_interception_amend_http_header(self):
        pass

    @sync
    async def test_request_interception_abort_main(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            await req.abort()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        with self.assertRaises(PageError) as cm:
            await self.page.goto(self.url + 'empty')
        self.assertEqual(cm.exception.args[0], 'net::ERR_FAILED')

    @unittest.skip('Failed to get response in redirect')
    @sync
    async def test_request_interception_redirects(self):
        await self.page.setRequestInterception(True)
        requests = []

        async def check(req):
            await req.continue_()
            requests.append(req)

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'redirect1')
        self.assertIn(response.status, [200, 304])

    @unittest.skip('This test is not implemented')
    @sync
    async def test_request_interception_abort_redirects(self):
        pass

    @unittest.skip('This test is not implemented')
    @sync
    async def test_request_interception_equal_requests(self):
        pass

    @sync
    async def test_request_interception_data_url(self):
        await self.page.setRequestInterception(True)
        requests = []

        async def check(req):
            requests.append(req)
            await req.continue_()

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        dataURL = 'data:text/html,<div>yo</div>'
        response = await self.page.goto(dataURL)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, dataURL)

    @sync
    async def test_request_interception_abort_data_url(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            await req.abort()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        with self.assertRaises(PageError) as cm:
            await self.page.goto('data:text/html,No way!')
        self.assertEqual(cm.exception.args[0], 'net::ERR_FAILED')

    @sync
    async def test_request_interception_with_hash(self):
        await self.page.setRequestInterception(True)
        requests = []

        async def check(req):
            requests.append(req)
            await req.continue_()

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'empty#hash')
        self.assertIn(response.status, [200, 304])
        self.assertEqual(response.url, self.url + 'empty')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, self.url + 'empty')

    @sync
    async def test_request_interception_encoded_server(self):
        await self.page.setRequestInterception(True)

        async def check(req):
            await req.continue_()

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'non existing page')
        self.assertEqual(response.status, 404)

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_request_interception_badly_encoded_server(self):
        pass

    @unittest.skip('Need server-side implementation')
    @sync
    async def test_request_interception_encoded_server_2(self):
        pass

    @unittest.skip('This test is not implemented')
    @sync
    async def test_request_interception_invalid_interception_id(self):
        pass

    @sync
    async def test_request_interception_disabled(self):
        error = None

        async def check(req):
            try:
                await req.continue_()
            except Exception as e:
                nonlocal error
                error = e

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        await self.page.goto(self.url + 'empty')
        self.assertIsNotNone(error)
        self.assertIn('Request interception is not enabled', error.args[0])

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

    @unittest.skip('Sending bynary object is not implemented')
    @sync
    async def test_request_respond_bytes(self):
        pass


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
        with self.assertRaises(PageError) as cm:
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
        self.assertIn(response.status, [200, 304])


class TestAuthenticateFaile(BaseTestCase):
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
        self.assertIn(response.status, [200, 304])
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


class TestAddScriptTag(BaseTestCase):
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
        self.assertEqual(await self.page.evaluate('() => window.__injected'), 42)  # noqa: E501

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
        scriptHandle = await self.page.addScriptTag(content='window.__injected = 35;')  # noqa: E501
        self.assertIsNotNone(scriptHandle.asElement())
        self.assertEqual(await self.page.evaluate('() => window.__injected'), 35)  # noqa: E501


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
