"""
Tests relating to page/frame navigation
"""
import pytest
from syncer import sync

from pyppeteer.errors import BrowserError, TimeoutError, NetworkError
from tests.utils import isFavicon
from tests.conftest import needs_server_side_implementation
from tests.utils import gather_with_timeout


class TestPage:
    class TestGoto:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            assert isolated_page.url == server.empty_page

        @sync
        async def test_works_with_anchor_nav(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            assert isolated_page.url == server.empty_page
            await isolated_page.goto(server.empty_page + '#foo')
            assert isolated_page.url == server.empty_page + '#foo'
            await isolated_page.goto(server.empty_page + '#bar')
            assert isolated_page.url == server.empty_page + '#bar'

        @sync
        @needs_server_side_implementation
        async def test_works_with_redirects(self, isolated_page, server):
            pass

        @sync
        async def test_navigates_to_aboutblank(self, isolated_page):
            resp = await isolated_page.goto('about:blank')
            assert resp is None

        @sync
        async def test_returns_resp_when_page_changes_url_on_load(self, isolated_page, server):
            resp = await isolated_page.goto(server / 'historyapi.html')
            assert resp.status == 200

        @sync
        @needs_server_side_implementation
        async def test_works_with_204_subframes(self, isolated_page, server):
            pass

        @sync
        @needs_server_side_implementation
        async def test_fail_when_server_204s(self, isolated_page, server):
            pass

        @sync
        async def test_navigates_to_empty_page_and_waits_until_domcontentloaded(self, isolated_page, server):
            resp = await isolated_page.goto(server.empty_page, waitUntil='domcontentloaded')
            assert resp.status == 200

        @sync
        async def test_navigates_to_empty_page_and_waits_until_networkidle0(self, isolated_page, server):
            resp = await isolated_page.goto(server.empty_page, waitUntil='networkidle0')
            assert resp.status == 200

        @sync
        async def test_navigates_to_empty_page_and_waits_until_networkidle2(self, isolated_page, server):
            resp = await isolated_page.goto(server.empty_page, waitUntil='networkidle2')
            assert resp.status == 200

        @sync
        async def test_should_work_when_page_calls_history_API_within_beforeunload(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.evaluate(
                '''() => {
                window.addEventListener('beforeunload', () => {
                        history.replaceState(null, 'initial', window.location.href)
                    }, 
                false);
            }'''
            )
            resp = await isolated_page.goto(server / 'grid.html')
            assert resp.status == 200

        @sync
        async def test_fails_on_bad_url(self, isolated_page):
            with pytest.raises(NetworkError) as excpt:
                await isolated_page.goto('yeet')
            assert 'invalid url' in str(excpt).lower()

        @sync
        async def test_fails_on_bad_ssl(self, isolated_page, server):
            # Make sure that network events do not emit 'undefined'.
            # @see https://crbug.com/750469
            def assert_truthy(o):
                assert o

            isolated_page.on('request', assert_truthy)
            isolated_page.on('requestfinished', assert_truthy)
            isolated_page.on('requestfailed', assert_truthy)
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto(server.https.empty_page)
            assert 'ERR_SSL_PROTOCOL_ERROR' in str(excpt) or 'SSL_ERROR_UNKNOWN' in str(excpt)

        @sync
        @needs_server_side_implementation
        async def test_fails_on_bad_ssl_redirects(self, isolated_page, server):
            pass

        @sync
        async def test_raises_on_deprecated_networkidle_waituntil(self, isolated_page, server):
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto(server.empty_page)
            assert 'no longer supported' in str(excpt)

        @sync
        async def test_fails_when_main_resources_fail_loading(self, isolated_page, server):
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto('http://localhost:27182/non-existing-url')
            assert 'CONNECTION_REFUSED' in str(excpt)

        @sync
        async def test_fails_on_exceeding_nav_timeout(self, isolated_page, server):
            server.app.add_one_time_request_delay(server.empty_page, 1)
            with pytest.raises(TimeoutError) as excpt:
                await isolated_page.goto(server.empty_page, timeout=1)
            assert 'navigation timeout' in str(excpt)

        @sync
        async def test_fails_on_exceeding_default_nav_timeout(self, isolated_page, server):
            server.app.add_one_time_request_delay(server.empty_page, 1)
            isolated_page.setDefaultNavigationTimeout(1)
            with pytest.raises(TimeoutError) as excpt:
                await isolated_page.goto(server.empty_page)
            assert 'navigation timeout' in str(excpt)

        @sync
        async def test_fails_on_exceeding_default_timeout(self, isolated_page, server):
            server.app.add_one_time_request_delay(server.empty_page, 1)
            isolated_page.setDefaultTimeout(1)
            with pytest.raises(TimeoutError) as excpt:
                await isolated_page.goto(server.empty_page)
            assert 'navigation timeout' in str(excpt)

        @sync
        async def test_prioritizes_nav_timeout_of_default(self, isolated_page, server):
            server.app.add_one_time_request_delay(server.empty_page, 1)
            isolated_page.setDefaultTimeout(0)
            isolated_page.setDefaultNavigationTimeout(1)
            with pytest.raises(TimeoutError) as excpt:
                await isolated_page.goto(server.empty_page)
            assert 'navigation timeout' in str(excpt)

        @sync
        async def test_timeout_disabled_when_equal_to_0(self, isolated_page, server):
            loaded = False

            def set_loaded():
                nonlocal loaded
                loaded = True

            isolated_page.once('load', set_loaded)
            await isolated_page.goto(server / 'grid.html', timeout=1, waitUntil='load')
            assert loaded

        @sync
        async def test_works_when_navigating_to_valid_data_url(self, isolated_page, server):
            assert (await isolated_page.goto('data:text/html,hello')).ok

        @sync
        async def test_works_when_navigating_to_404(self, isolated_page, server):
            resp = await isolated_page.goto(server / 'not-found')
            assert resp.ok is False
            assert resp.status == 404

        @sync
        @needs_server_side_implementation
        async def test_returns_last_response_in_redirect_chain(self, isolated_page, server):
            pass

        @sync

        async def test_wait_for_network_idle_for_nav_to_succeed(self, isolated_page, server):
            pass



        @sync
        async def test_does_not_leak_listeners_during_nav(self, isolated_page, server):
            pass

        @sync
        async def test_does_not_leak_listeners_during_bad_nav(self, isolated_page, server):
            pass

        @sync
        async def test_does_not_leak_listeners_during_nav_of_many_pages(self, isolated_page, server):
            pass

        @sync
        async def test_navs_to_dataURL_and_fires_dataURL_reqs(self, isolated_page, server):
            requests = []

            def append_req(r):
                nonlocal requests
                if not isFavicon(r):
                    requests.append(r)

            isolated_page.on('request', append_req)
            data_url = 'data:text/html,<div>yo</div>'
            resp = await isolated_page.goto(data_url)
            assert resp.status == 200
            assert len(requests) == 1
            assert requests[0].url == data_url

        @sync
        async def test_navigates_to_url_with_hash_and_fires_events_without_hash(self, isolated_page, server):
            requests = []

            def append_req(r):
                nonlocal requests
                if not isFavicon(r):
                    requests.append(r)

            isolated_page.on('request', append_req)
            # todo: test url join on hash
            resp = await isolated_page.goto(server.empty_page / '#hash')
            assert resp.status == 200
            assert resp.url == server.empty_page
            assert len(requests) == 1
            assert requests[0].url == server.empty_page

        @sync
        async def test_works_with_self_requesting_pages(self, isolated_page, server):
            resp = await isolated_page.goto(server.empty_page / 'self-request.html')
            assert resp.status == 200
            assert 'self-request' in resp.url

        @sync
        async def test_shows_proper_error_msg_on_failed_nav(self, isolated_page, server):
            url = server.https / 'redirect/1.html'
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto(url)
            assert url in str(excpt)

        @sync
        async def test_sends_referer(self, isolated_page, server):
            req1, req2, *_ = await gather_with_timeout(
                server.app.waitForRequest('/grid.html'),
                server.app.waitForRequest('/digits/1.png'),
                isolated_page.goto(server / 'grid.html', referer='http://google.com'),
            )
            assert req1.headers.get('referer') == 'http://google.com'
            assert req2.headers.get('referer') == server / 'grid.html'

    class TestWaitForNavigation:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_both_domcontentloaded_and_load(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_clicking_anchor_urls(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_historypushState(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_historyreplaceState(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_historyback_forward(self, isolated_page, server):
            pass

        @sync
        async def test_works_when_subframe_runs_windowstop(self, isolated_page, server):
            pass

    class TestGoBack:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            pass

        @sync
        async def test_works_with_historyAPI(self, isolated_page, server):
            pass

    @sync
    async def test_reload_works(self, isolated_page, server):
        pass


class Frame:
    class TestGoto:
        @sync
        async def test_navigates_subframes(self, isolated_page, server):
            pass

        @sync
        async def test_rejects_when_frame_detaches(self, isolated_page, server):
            pass

        @sync
        async def test_returns_matching_responses(self, isolated_page, server):
            pass

    class TestWaitForNavigation:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            pass

        @sync
        async def test_fails_when_frame_detaches(self, isolated_page, server):
            pass
