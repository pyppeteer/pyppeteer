import asyncio
import itertools
from contextlib import suppress

import pytest
from pyppeteer.errors import BrowserError
from syncer import sync
from tests import utils
from tests.utils import isFavicon, var_setter


async def request_continuer(request):
    await request.continue_()


class TestPageSetRequestInterception:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        def request_checker(request):
            if not isFavicon(request):
                assert 'empty.html' in request.url
                assert request.headers['user-agent']
                assert request.method == 'GET'
                assert request.postData is None
                assert request.isNavigationRequest
                assert request.resourceType == 'document'
                assert request.frame == isolated_page.mainFrame
                assert request.frame.url == 'about:blank'
            request.continue_()

        resp = await isolated_page.goto(server.empty_page)
        assert resp.ok
        assert resp.remoteAddress['port'] == server.port

    # see https://github.com/puppeteer/puppeteer/issues/3973
    @sync
    @pytest.mark.skip(reason='needs server side implementation')
    async def test_works_when_POST_redirects_with_302(self, isolated_page, server):
        server.app.one_time_redirect('/rredirect', '/empty.html')
        await isolated_page.goto(server.empty_page)
        await isolated_page.setRequestInterception(True)

        isolated_page.on('request', request_continuer)

        await isolated_page.setContent(
            '''
            <form action='/rredirect' method='post'>
                <input type="hidden" id="foo" name="foo" value="FOOBAR">
            </form>
        '''
        )
        await asyncio.gather(isolated_page.Jeval('form', 'f => f.submit()'), isolated_page.waitForNavigation())

    @sync
    async def test_works_with_header_manipulation_and_redirect(self, isolated_page, server):
        server.app.one_time_redirect('/rrredirect', '/button.html')
        await isolated_page.setRequestInterception(True)
        await isolated_page.goto(server.empty_page)

        @isolated_page.on('request')
        async def header_manipulator(request):
            headers = {**request.headers, 'foo': 'bar'}
            await request.continue_(headers=headers)

        await isolated_page.goto(server / 'rrredirect')

    # see https://github.com/puppeteer/puppeteer/issues/4743
    @sync
    async def test_is_able_to_remove_headers(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def header_manipulator(request):
            # ie, origin header won't be sent
            headers = {**request.headers, 'origin': None}
            await request.continue_(headers=headers)

        server_req, *_ = await asyncio.gather(
            server.app.waitForRequest('/empty.html'), isolated_page.goto(server.empty_page),
        )

        assert server_req.headers.get('origin') is None

    @sync
    async def test_contains_referer_header(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def adder(req):
            if not utils.isFavicon(req):
                requests.append(req)
            await req.continue_()

        await isolated_page.goto(server / 'one-style.html')
        assert 'one-style.css' in requests[1].url
        assert 'one-style.html' in requests[1].headers['referer']

    @sync
    async def test_properly_returns_nav_response_when_URL_has_cookies(self, isolated_page, server):
        # setup cookie
        await isolated_page.goto(server.empty_page)
        await isolated_page.setCookie({'name': 'foor', 'value': 'bar'})

        # setup request intercept
        await isolated_page.setRequestInterception(True)
        isolated_page.on('request', request_continuer)
        resp = await isolated_page.reload()
        assert resp.status == 200

    @sync
    async def test_stop_interception(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        isolated_page.once('request', request_continuer)
        await isolated_page.goto(server)
        await isolated_page.setRequestInterception(False)
        await isolated_page.goto(server)

    @sync
    async def test_shows_custom_HTTP_headers(self, isolated_page, server):
        await isolated_page.setExtraHTTPHeaders({'foo': 'bar'})
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def header_checker(req):
            assert req.headers['foo'] == 'bar'
            await req.continue_()

        resp = await isolated_page.goto(server)
        assert resp.ok

    # see https://github.com/puppeteer/puppeteer/issues/4337
    @sync
    async def test_works_with_redirect_within_synchronous_XHR(self, isolated_page, server):
        await isolated_page.goto(server)
        server.app.one_time_redirect('/logo.png', '/pptr.png')
        await isolated_page.setRequestInterception(True)
        isolated_page.on('request', request_continuer)
        status = await isolated_page.evaluate(
            '''async() => {
            const request = new XMLHttpRequest();
            request.open('GET', '/logo.png', false);  // `false` makes the request synchronous
            request.send(null);
            return request.status;
        }'''
        )
        assert status == 200

    @sync
    async def test_works_with_custom_referer_headers(self, isolated_page, server):
        await isolated_page.setExtraHTTPHeaders({'referer': server.empty_page})
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def request_checker(req):
            assert req.headers['referer'] == server.empty_page
            await req.continue_()

        resp = await isolated_page.goto(server)
        assert resp.ok

    @sync
    async def test_abortability(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def request_aborter(req):
            if req.url.endswith('.css'):
                await req.abort()
            else:
                await req.continue_()

        failed_reqs = itertools.count()

        isolated_page.on('requestfailed', lambda _: next(failed_reqs))
        resp = await isolated_page.goto(server / 'one-style.html')
        assert resp.ok
        assert resp.request.failure is None
        assert next(failed_reqs) - 1 == 1

    @sync
    async def test_abortability_with_custom_error_codes(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def request_aborter(req):
            await req.abort('internetdisconnected')

        failed_req = None
        isolated_page.on('requestfailed', var_setter('var_setter'))
        with suppress(BrowserError):
            await isolated_page.goto(server)

        assert failed_req is not None
        # noinspection PyUnresolvedReferences
        assert failed_req.failure.errorText == 'net::ERR_INTERNET_DISCONNECTED'

    @sync
    async def test_sends_referer(self, isolated_page, server):
        referer = 'http://google.com/'
        await isolated_page.setExtraHTTPHeaders({'referer': referer})
        await isolated_page.setRequestInterception(True)
        isolated_page.on('request', request_continuer)
        request, *_ = asyncio.gather(server.app.waitForRequest('/grid.html'), isolated_page.goto(server / 'grid.html'))
        assert request.headers.get('referer') == referer

    @sync
    async def test_fails_navigation_when_aborting_main_resource(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        @isolated_page.on('request')
        async def request_aborter(req):
            await req.abort()

        with pytest.raises(BrowserError, match='(net::ERR_FAILED|NS_ERROR_FAILURE)'):
            await isolated_page.goto(server)

    @sync
    async def test_works_with_redirects(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def request_logger(req):
            await req.continue_()
            requests.append(req)

        server.app.one_time_redirect('/non-existing-page.html', '/non-existing-page-2.html')
        server.app.one_time_redirect('/non-existing-page-2.html', '/non-existing-page-3.html')
        server.app.one_time_redirect('/non-existing-page-3.html', '/non-existing-page-4.html')
        server.app.one_time_redirect('/non-existing-page-4.html', '/empty.html')

        resp = await isolated_page.goto(server / 'non-existing-page.html')
        assert resp.status == 200
        assert 'empty.html' in resp.url
        assert len(requests) == 5
        assert requests[2].resourceType == 'document'
        # check redirect chain
        redirect_chain = resp.request.redirectChain
        assert len(redirect_chain) == 4
        assert '-page' in redirect_chain[0].url
        assert '-page-3' in redirect_chain[2].url

        for index, redirect in enumerate(redirect_chain):
            assert redirect.isNavigationRequest
            assert redirect.redirectChain.index(redirect)

    @sync
    async def test_works_with_redirects_for_subresources(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def request_logger(req):
            await req.continue_()
            if not utils.isFavicon(req):
                requests.append(req)

        end_of_chain_resp = 'body {box-sizing: border-box; }'
        server.app.one_time_redirect('/one-style.css', '/two-style.css')
        server.app.one_time_redirect('/two-style.css', '/three-style.css')
        server.app.one_time_redirect('/three-style.css', '/four-style.css')
        server.app.add_one_time_request_resp('/four-style.css', end_of_chain_resp)

        resp = await isolated_page.goto(server / 'one-style.html')
        assert resp.status == 200
        assert 'one-style.html' in resp.url
        assert len(requests) == 5
        assert requests[0].resourceType == 'document'
        assert requests[1].resourceType == 'stylesheet'
        assert await requests[-1].response.text == end_of_chain_resp

        # check redirect chain
        redirect_chain = await requests[1].redirectChain
        assert len(redirect_chain) == 3
        assert 'one-style.css' in redirect_chain[0].url
        assert 'three-style.css' in redirect_chain[2].url

    @sync
    async def test_redirection_abortibility(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        server.app.setRedirect('/non-existing.json', '/non-existing-2.json')
        server.app.setRedirect('/non-existing-2.json', '/simple.html')

        @isolated_page.on('request')
        async def request_aborter(req):
            if 'non-existing-2' in req.url:
                await req.abort()
            else:
                await req.continue_()

        await isolated_page.goto(server.empty_page)
        res = await isolated_page.evaluate(
            '''async() => {
            try {
                await fetch('/non-existing.json');
            } catch (e) {
                return e.message;
            }
        }'''
        )
        assert 'Failed to fetch' in res or 'NetworkError' in res

    @sync
    async def test_works_with_equal_requests(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        response_count = 1

        async def server_response_handler(handler):
            nonlocal response_count
            await handler.write(f'{response_count*11}')
            response_count += 1

        server.app.add_one_time_request_precondition('/zzz', server_response_handler)
        await isolated_page.setRequestInterception(True)

        spinner = False

        @isolated_page.on('request')
        async def request_aborter(req):
            nonlocal spinner
            if utils.isFavicon(req) or spinner:
                await req.continue_()
            elif spinner:
                await req.abort()
            spinner = not spinner

        results = await isolated_page.evaluate(
            '''() => Promise.all([
            fetch('/zzz').then(response => response.text()).catch(e => 'FAILED'),
            fetch('/zzz').then(response => response.text()).catch(e => 'FAILED'),
            fetch('/zzz').then(response => response.text()).catch(e => 'FAILED'),
        ])'''
        )
        assert results == ['11', 'FAILED', '22']

    @sync
    async def test_navigates_to_dataURL_and_fires_dataURL_requests(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def request_logger(req):
            requests.append(req)
            await req.continue_()

        dataURL = 'data:text/html,<div>yo</div>'
        response = await isolated_page.goto(dataURL)
        assert response.status == 200
        assert len(requests) == 1
        assert requests[0].url == dataURL

    @sync
    async def test_fetches_dataURL_and_fires_dataURL_requests(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def request_logger(req):
            requests.append(req)
            await req.continue_()

        dataURL = 'data:text/html,<div>yo</div>'
        text = await isolated_page.evaluate('url => fetch(url).then(r => r.text())', dataURL)
        assert text == '<div>yo</div>'
        assert len(requests) == 1
        assert requests[0].url == dataURL

    @sync
    async def test_navigates_to_URL_with_hash_and_fires_request_without_hash(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)
        requests = []

        @isolated_page.on('request')
        async def request_logger(req):
            requests.append(req)
            await req.continue_()

        response = await isolated_page.goto(server.empty_page + '#hash')
        assert response.status == 200
        assert response.url == server.empty_page
        assert len(requests) == 1
        assert requests[0].url == server.empty_page

    @sync
    async def test_works_with_encoded_server_url(self, isolated_page, server):
        # The requestWillBeSent will report encoded URL, whereas interception will
        # report URL as-is. see crbug.com/759388
        await isolated_page.setRequestInterception(True)
        isolated_page.on('request', request_continuer)
        resp = await isolated_page.goto(server / 'some nonexistant page, somewhere')
        assert resp.status == 404

    @sync
    async def test_works_with_another_encoded_server_url(self, isolated_page, server):
        # The requestWillBeSent will report URL as-is, whereas interception will
        # report encoded URL for stylesheet. @see crbug.com/759388
        await isolated_page.setRequestInterception(True)
        isolated_page.on('request', request_continuer)
        resp = await isolated_page.goto(server / 'some nonexistant page, somewhere')
        assert resp.status == 404

    @sync
    async def test_works_with_badly_encoded_server(self, isolated_page, server):
        await isolated_page.setRequestInterception(True)

        # todo: define __str__ for server
        resp = await isolated_page.goto(
            f'data:text/html,<link rel="stylesheet" href="{server}/fonts?helvetica|arial"/>'
        )
        assert resp.status == 200
        assert len(requests) == 2
        assert requests[1].response.status == 404

    @sync
    async def test_doesnt_raise_on_request_cancellation(self, isolated_page, server):
        await isolated_page.setContent('<iframe></iframe>')
        await isolated_page.setRequestInterception(True)

        request = None
        isolated_page.on('request', var_setter('request'))
        await isolated_page.Jeval('iframe', '(frame, url) => frame.src = url', server.empty_page)
        # wait for request to be intercepted
        await utils.waitEvent(isolated_page, 'request')
        # delete frame to cause request to be canceled
        await isolated_page.Jeval('iframe', 'frame => frame.remove()')
        with pytest.raises(BrowserError):
            # noinspection PyUnresolvedReferences
            await request.continue_()

    @sync
    async def test_raises_if_interception_not_enabled(self, isolated_page, server):
        error = None

        @isolated_page.on('request')
        def request_continuer_error_catch(req):
            nonlocal error
            try:
                await req.continue_()
            except Exception as error:
                pass

        await isolated_page.goto(server.empty_page)
        assert 'Request Interception is not enabled' in str(error)

    @sync
    async def test_works_with_file_URLs(self, isolated_page, assets):
        await isolated_page.setRequestInterception(True)
        urls = set()

        @isolated_page.on('request')
        async def request_logger(req):
            urls.add(req.split('/')[-1])
            await req.continue_()

        await isolated_page.goto(assets / 'one-style.html')
        assert len(urls) == 2
        assert {'one-style.html', 'one-style.css'} == urls


class TestRequestContinue:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        pass

    @sync
    async def test_amends_HTTP_headers(self, isolated_page, server):
        pass

    @sync
    async def test_redirects_are_inobservable_by_page(self, isolated_page, server):
        pass

    @sync
    async def test_amends_method(self, isolated_page, server):
        pass

    @sync
    async def test_amends_POST_data(self, isolated_page, server):
        pass

    @sync
    async def test_amends_both_POST_data_and_method_on_nav(self, isolated_page, server):
        pass


class TestRequestRespond:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_status_code_422(self, isolated_page, server):
        pass

    @sync
    async def test_executes_redirects(self, isolated_page, server):
        pass

    @sync
    async def test_allowance_of_mocking_binary_responses(self, isolated_page, server):
        pass

    @sync
    async def test_stringifies_intercepted_request_response_headers(self, isolated_page, server):
        pass
