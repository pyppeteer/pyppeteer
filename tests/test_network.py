#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from pathlib import Path
import sys
import unittest

from syncer import sync

from pyppeteer.errors import NetworkError, PageError

from .base import BaseTestCase


class TestNetworkEvent(BaseTestCase):
    @sync
    async def test_request(self):
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        await self.page.goto(self.url + 'empty')
        self.assertEqual(len(requests), 1)
        req = requests[0]
        self.assertEqual(req.url, self.url + 'empty')
        self.assertEqual(req.resourceType, 'document')
        self.assertEqual(req.method, 'GET')
        self.assertTrue(req.response)
        self.assertEqual(req.frame, self.page.mainFrame)
        self.assertEqual(req.frame.url, self.url + 'empty')

    @sync
    async def test_request_post(self):
        await self.page.goto(self.url + 'empty')

        from tornado.web import RequestHandler

        class PostHandler(RequestHandler):
            def post(self):
                self.write('')

        self.app.add_handlers('localhost', [('/post', PostHandler)])
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        await self.page.evaluate('fetch("/post", {method: "POST", body: JSON.stringify({foo: "bar"})})')  # noqa: E501
        self.assertEqual(len(requests), 1)
        req = requests[0]
        self.assertTrue(req)
        self.assertEqual(req.postData, '{"foo":"bar"}')

    @sync
    async def test_response(self):
        responses = []
        self.page.on('response', lambda res: responses.append(res))
        await self.page.goto(self.url + 'empty')
        self.assertEqual(len(responses), 1)
        response = responses[0]
        self.assertEqual(response.url, self.url + 'empty')
        self.assertEqual(response.status, 200)
        # self.assertTrue(response.ok)
        self.assertFalse(response.fromCache)
        self.assertFalse(response.fromServiceWorker)
        self.assertTrue(response.request)
        self.assertEqual(response.securityDetails, {})

    @sync
    async def test_response_https(self):
        responses = []
        self.page.on('response', lambda res: responses.append(res))
        await self.page.goto('https://example.com/')
        self.assertEqual(len(responses), 1)
        response = responses[0]
        self.assertEqual(response.url, 'https://example.com/')
        self.assertEqual(response.status, 200)
        self.assertTrue(response.ok)
        self.assertFalse(response.fromCache)
        self.assertFalse(response.fromServiceWorker)
        self.assertTrue(response.request)
        self.assertTrue(response.securityDetails)
        self.assertEqual(response.securityDetails.protocol, 'TLS 1.2')

    @sync
    async def test_from_cache(self):
        responses = {}

        def set_response(resp):
            basename = resp.url.split('/').pop()
            responses[basename] = resp

        self.page.on('response', set_response)

        await self.page.goto(self.url + 'static/cached/one-style.html')
        await self.page.reload()

        self.assertEqual(len(responses), 2)
        self.assertEqual(responses['one-style.html'].status, 304)
        self.assertFalse(responses['one-style.html'].fromCache)
        self.assertEqual(responses['one-style.css'].status, 200)
        self.assertTrue(responses['one-style.css'].fromCache)

    @sync
    async def test_response_from_service_worker(self):
        responses = {}

        def set_response(resp):
            basename = resp.url.split('/').pop()
            responses[basename] = resp

        self.page.on('response', set_response)

        await self.page.goto(
            self.url + 'static/serviceworkers/fetch/sw.html',
            waitUntil='networkidle2',
        )
        await self.page.evaluate('async() => await window.activationPromise')
        await self.page.reload()

        self.assertEqual(len(responses), 2)
        self.assertEqual(responses['sw.html'].status, 200)
        self.assertTrue(responses['sw.html'].fromServiceWorker)
        self.assertEqual(responses['style.css'].status, 200)
        self.assertTrue(responses['style.css'].fromServiceWorker)

    @unittest.skipIf(sys.platform.startswith('msys'), 'Fails on MSYS')
    @sync
    async def test_response_body(self):
        responses = []
        self.page.on('response', lambda res: responses.append(res))
        await self.page.goto(self.url + 'static/simple.json')
        self.assertEqual(len(responses), 1)
        res = responses[0]
        self.assertTrue(res)
        self.assertEqual(await res.text(), '{"foo": "bar"}\n')
        self.assertEqual(await res.json(), {'foo': 'bar'})

    @sync
    async def test_fail_get_redirected_body(self):
        response = await self.page.goto(self.url + 'redirect1')
        redirectChain = response.request.redirectChain
        self.assertEqual(len(redirectChain), 1)
        redirected = redirectChain[0].response
        self.assertEqual(redirected.status, 302)
        with self.assertRaises(NetworkError) as cm:
            await redirected.text()
        self.assertIn(
            'Response body is unavailable for redirect response',
            cm.exception.args[0],
        )

    @unittest.skip('This test hangs')
    @sync
    async def test_not_report_body_unless_finished(self):
        await self.page.goto(self.url + 'empty')
        serverResponses = []

        from tornado.web import RequestHandler

        class GetHandler(RequestHandler):
            def get(self):
                serverResponses.append(self)
                self.write('hello ')

        self.app.add_handlers('localhost', [('/get', GetHandler)])
        pageResponse = asyncio.get_event_loop().create_future()
        finishedRequests = []
        self.page.on('response', lambda res: pageResponse.set_result(res))
        self.page.on('requestfinished', lambda: finishedRequests.append(True))

        asyncio.ensure_future(
            self.page.evaluate('fetch("./get", {method: "GET"})'))
        response = await pageResponse
        self.assertTrue(serverResponses)
        self.assertTrue(response)
        self.assertEqual(response.status, 200)
        self.assertFalse(finishedRequests)

        responseText = response.text()
        serverResponses[0].write('wor')
        serverResponses[0].finish('ld!')
        self.assertEqual(await responseText, 'hello world!')

    @sync
    async def test_request_failed(self):
        await self.page.setRequestInterception(True)

        async def interception(req):
            if req.url.endswith('css'):
                await req.abort()
            else:
                await req.continue_()

        self.page.on(
            'request', lambda req: asyncio.ensure_future(interception(req)))

        failedRequests = []
        self.page.on('requestfailed', lambda req: failedRequests.append(req))
        await self.page.goto(self.url + 'static/one-style.html')
        self.assertEqual(len(failedRequests), 1)
        self.assertIn('one-style.css', failedRequests[0].url)
        self.assertIsNone(failedRequests[0].response)
        self.assertEqual(failedRequests[0].resourceType, 'stylesheet')
        self.assertEqual(
            failedRequests[0].failure()['errorText'], 'net::ERR_FAILED')
        self.assertTrue(failedRequests[0].frame)

    @sync
    async def test_request_finished(self):
        requests = []
        self.page.on('requestfinished', lambda req: requests.append(req))
        await self.page.goto(self.url + 'empty')

        self.assertEqual(len(requests), 1)
        req = requests[0]
        self.assertEqual(req.url, self.url + 'empty')
        self.assertTrue(req.response)
        self.assertEqual(req.frame, self.page.mainFrame)
        self.assertEqual(req.frame.url, self.url + 'empty')

    @sync
    async def test_events_order(self):
        events = []
        self.page.on('request', lambda req: events.append('request'))
        self.page.on('response', lambda res: events.append('response'))
        self.page.on(
            'requestfinished', lambda req: events.append('requestfinished'))
        await self.page.goto(self.url + 'empty')
        self.assertEqual(events, ['request', 'response', 'requestfinished'])

    @sync
    async def test_redirects(self):
        events = []
        self.page.on('request', lambda req: events.append(
            '{} {}'.format(req.method, req.url)))
        self.page.on('response', lambda res: events.append(
            '{} {}'.format(res.status, res.url)))
        self.page.on('requestfinished', lambda req: events.append(
            'DONE {}'.format(req.url)))
        self.page.on('requestfailed', lambda req: events.append(
            'FAIL {}'.format(req.url)))
        response = await self.page.goto(self.url + 'redirect1')
        self.assertEqual(events, [
            'GET {}'.format(self.url + 'redirect1'),
            '302 {}'.format(self.url + 'redirect1'),
            'DONE {}'.format(self.url + 'redirect1'),
            'GET {}'.format(self.url + 'redirect2'),
            '200 {}'.format(self.url + 'redirect2'),
            'DONE {}'.format(self.url + 'redirect2'),
        ])

        # check redirect chain
        redirectChain = response.request.redirectChain
        self.assertEqual(len(redirectChain), 1)
        self.assertIn('redirect1', redirectChain[0].url)


class TestRequestInterception(BaseTestCase):
    @sync
    async def test_request_interception(self):
        await self.page.setRequestInterception(True)

        async def request_check(req):
            self.assertIn('empty', req.url)
            self.assertTrue(req.headers.get('user-agent'))
            self.assertEqual(req.method, 'GET')
            self.assertIsNone(req.postData)
            self.assertTrue(req.isNavigationRequest())
            self.assertEqual(req.resourceType, 'document')
            self.assertEqual(req.frame, self.page.mainFrame)
            self.assertEqual(req.frame.url, 'about:blank')
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(request_check(req)))
        res = await self.page.goto(self.url + 'empty')
        self.assertEqual(res.status, 200)

    @sync
    async def test_referer_header(self):
        await self.page.setRequestInterception(True)
        requests = list()

        async def set_request(req):
            requests.append(req)
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(set_request(req)))
        await self.page.goto(self.url + 'static/one-style.html')
        self.assertIn('/one-style.css', requests[1].url)
        self.assertIn('/one-style.html', requests[1].headers['referer'])

    @sync
    async def test_response_with_cookie(self):
        await self.page.goto(self.url + 'empty')
        await self.page.setCookie({'name': 'foo', 'value': 'bar'})

        await self.page.setRequestInterception(True)

        async def continue_(req):
            await req.continue_()

        self.page.on('request', lambda r: asyncio.ensure_future(continue_(r)))
        response = await self.page.reload()
        self.assertEqual(response.status, 200)

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
        self.assertEqual(res.status, 200)

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
        self.assertEqual(res.status, 200)

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
        self.assertIn('net::ERR_FAILED', cm.exception.args[0])

    @sync
    async def test_request_interception_redirects(self):
        await self.page.setRequestInterception(True)
        requests = []

        async def check(req):
            await req.continue_()
            requests.append(req)

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'redirect1')
        self.assertEqual(response.status, 200)

    @sync
    async def test_redirect_for_subresource(self):
        await self.page.setRequestInterception(True)
        requests = list()

        async def check(req):
            await req.continue_()
            requests.append(req)

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'one-style.html')
        self.assertEqual(response.status, 200)
        self.assertIn('one-style.html', response.url)
        self.assertEqual(len(requests), 5)
        self.assertEqual(requests[0].resourceType, 'document')
        self.assertEqual(requests[1].resourceType, 'stylesheet')

        # check redirect chain
        redirectChain = requests[1].redirectChain
        self.assertEqual(len(redirectChain), 3)
        self.assertIn('/one-style.css', redirectChain[0].url)
        self.assertIn('/three-style.css', redirectChain[2].url)

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
        self.assertIn('net::ERR_FAILED', cm.exception.args[0])

    @sync
    async def test_request_interception_with_hash(self):
        await self.page.setRequestInterception(True)
        requests = []

        async def check(req):
            requests.append(req)
            await req.continue_()

        self.page.on('request', lambda req: asyncio.ensure_future(check(req)))
        response = await self.page.goto(self.url + 'empty#hash')
        self.assertEqual(response.status, 200)
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
    async def test_request_interception_with_file_url(self):
        await self.page.setRequestInterception(True)
        urls = []

        async def set_urls(req):
            urls.append(req.url.split('/').pop())
            await req.continue_()

        self.page.on(
            'request', lambda req: asyncio.ensure_future(set_urls(req)))

        def pathToFileURL(path: Path):
            pathName = str(path).replace('\\', '/')
            if not pathName.startswith('/'):
                pathName = '/{}'.format(pathName)
            return 'file://{}'.format(pathName)

        target = Path(__file__).parent / 'static' / 'one-style.html'
        await self.page.goto(pathToFileURL(target))
        self.assertEqual(len(urls), 2)
        self.assertIn('one-style.html', urls)
        self.assertIn('one-style.css', urls)

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

    @unittest.skip('Sending binary object is not implemented')
    @sync
    async def test_request_respond_bytes(self):
        pass


class TestNavigationRequest(BaseTestCase):
    @sync
    async def test_navigation_request(self):
        requests = dict()

        def set_request(req):
            requests[req.url.split('/').pop()] = req

        self.page.on('request', set_request)
        await self.page.goto(self.url + 'redirect3')
        self.assertTrue(requests['redirect3'].isNavigationRequest())
        self.assertTrue(requests['one-frame.html'].isNavigationRequest())
        self.assertTrue(requests['frame.html'].isNavigationRequest())
        self.assertFalse(requests['script.js'].isNavigationRequest())
        self.assertFalse(requests['style.css'].isNavigationRequest())

    @sync
    async def test_interception(self):
        requests = dict()

        async def on_request(req):
            requests[req.url.split('/').pop()] = req
            await req.continue_()

        self.page.on('request',
                     lambda req: asyncio.ensure_future(on_request(req)))

        await self.page.setRequestInterception(True)
        await self.page.goto(self.url + 'redirect3')
        self.assertTrue(requests['redirect3'].isNavigationRequest())
        self.assertTrue(requests['one-frame.html'].isNavigationRequest())
        self.assertTrue(requests['frame.html'].isNavigationRequest())
        self.assertFalse(requests['script.js'].isNavigationRequest())
        self.assertFalse(requests['style.css'].isNavigationRequest())

    @sync
    async def test_image(self):
        requests = []
        self.page.on('request', lambda req: requests.append(req))
        await self.page.goto(self.url + 'static/huge-image.png')
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].isNavigationRequest())
