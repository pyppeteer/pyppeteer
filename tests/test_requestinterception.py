import asyncio

import pytest
from syncer import sync
from tests.utils import isFavicon


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
        isolated_page.on('request', lambda r: r.continue_())
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
        def header_manipulator(request):
            headers = {**request.headers, 'foo': 'bar'}
            request.continue_(headers=headers)

        await isolated_page.goto(server / 'rrredirect')

    # see https://github.com/puppeteer/puppeteer/issues/4743
    @sync
    async def test_is_able_to_remove_headers(self, isolated_page, server):
        @isolated_page.on('request')
        def header_manipulator(request):
            # ie, origin header won't be sent
            headers = {**request.headers, 'origin': None}
            request.continue_(headers=headers)

        server_req, *_ = await asyncio.gather(
            server.app.waitForRequest('/empty.html'), isolated_page.goto(server.empty_page),
        )

        assert server_req.headers.get('origin') is None

    @sync
    async def test_contains_referer_header(self, isolated_page, server):
        pass

    @sync
    async def test_properly_returns_nav_response_when_URL_has_cookies(self, isolated_page, server):
        pass

    @sync
    async def test_stop_interception(self, isolated_page, server):
        pass

    @sync
    async def test_shows_custom_HTTP_headers(self, isolated_page, server):
        pass

    # see https://github.com/puppeteer/puppeteer/issues/4337
    @sync
    async def test_works_with_redirect_within_synchronous_XHR(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_custom_referer_headers(self, isolated_page, server):
        pass

    @sync
    async def test_abortability(self, isolated_page, server):
        pass

    @sync
    async def test_abortability_with_custom_error_codes(self, isolated_page, server):
        pass

    @sync
    async def test_sends_referer(self, isolated_page, server):
        pass

    @sync
    async def test_fails_navigation_when_aborting_main_resource(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_redirects(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_redirects_for_subresources(self, isolated_page, server):
        pass

    @sync
    async def test_redirection_abortibility(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_equal_requests(self, isolated_page, server):
        pass

    @sync
    async def test_navigates_to_dataURL_and_fires_dataURL_requests(self, isolated_page, server):
        pass

    @sync
    async def test_fetches_dataURL_and_fires_dataURL_requests(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_encoded_server(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_another_encoded_server(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_badly_encoded_server(self, isolated_page, server):
        pass

    @sync
    async def test_doesnt_raise_on_request_cancellation(self, isolated_page, server):
        pass

    @sync
    async def test_raises_if_interception_not_enabled(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_file_URLs(self, isolated_page):
        pass


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
