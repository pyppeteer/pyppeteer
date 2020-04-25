from syncer import sync


class TestPageSetRequestInterception:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        pass

    @sync
    async def test_works_when_POST_redirects_with_302(self, isolated_page, server):
        pass

    @sync
    async def test_works_with_header_manipulation_and_redirect(self, isolated_page, server):
        pass

    @sync
    async def test_is_able_to_remove_headers(self, isolated_page, server):
        pass

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
