"""
Tests relating to page/frame navigation
"""
import asyncio
import re
from contextlib import suppress

import pytest
import tests.utils.server
from aiohttp import web
from pyppeteer.errors import BrowserError, NetworkError, PageError, TimeoutError
from pyppeteer.helpers import waitForEvent
from syncer import sync
from tests.conftest import needs_server_side_implementation
from tests.utils import attachFrame, gather_with_timeout, isFavicon, var_setter, waitEvent

NAV_TIMEOUT_MATCH = re.compile('navigation timeout', re.IGNORECASE)


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
        async def test_works_with_redirects(self, isolated_page, server):
            server.app.set_one_time_redirects('/redirect/1.html', '/redirect/2.html', server.empty_page)
            await isolated_page.goto(server / 'redirect/1.html')
            assert isolated_page.url == server.empty_page

        @sync
        async def test_navigates_to_aboutblank(self, isolated_page):
            resp = await isolated_page.goto('about:blank')
            assert resp is None

        @sync
        async def test_returns_resp_when_page_changes_url_on_load(self, isolated_page, server):
            resp = await isolated_page.goto(server / 'historyapi.html')
            assert resp.status == 200

        @sync
        async def test_works_with_204_subframes(self, isolated_page, server):
            server.app.set_one_time_response('/frames/frame.html', status=204)
            await isolated_page.goto(server / 'frames/one-frame.html')

        @sync
        @pytest.mark.skip
        async def test_fail_when_server_204s(self, isolated_page, server):
            server.app.set_one_time_response(server.empty_page, response='', status=204)
            with pytest.raises(BrowserError, match='_ABORTED'):
                await isolated_page.goto(server.empty_page)

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
            with pytest.raises(NetworkError, match='invalid URL'):
                await isolated_page.goto('yeet')

        @sync
        async def test_fails_on_bad_ssl(self, isolated_page, server):
            # Make sure that network events do not emit 'undefined'.
            # @see https://crbug.com/750469
            @isolated_page.on('request')
            @isolated_page.on('requestfinished')
            @isolated_page.on('requestfailed')
            def assert_truthy(req):
                assert req

            with pytest.raises(BrowserError, match='(ERR_CERT_AUTHORITY_INVALID|SSL_ERROR_UNKNOWN)'):
                await isolated_page.goto(server.https.empty_page)

        @sync
        async def test_fails_on_bad_ssl_redirects(self, isolated_page, server):
            # Make sure that network events do not emit 'undefined'.
            # @see https://crbug.com/750469
            @isolated_page.on('request')
            @isolated_page.on('requestfailed')
            @isolated_page.on('requestfinished')
            async def request_checker(req):
                assert req

            server.app.set_one_time_redirects('/redirect/1.html', '/redirect/2.html', server.empty_page)

            with pytest.raises(BrowserError, match=r'(SSL_ERROR_UNKNOWN|ERR_CERT_AUTHORITY_INVALID)'):
                await isolated_page.goto(server.https.empty_page)

        @sync
        async def test_raises_on_deprecated_networkidle_waituntil(self, isolated_page, server):
            with pytest.raises(KeyError, match='no longer supported'):
                await isolated_page.goto(server.empty_page, waitUntil='networkidle')

        @sync
        async def test_fails_when_main_resources_fail_loading(self, isolated_page, server):
            with pytest.raises(BrowserError, match='(ERR|NS_ERROR)_CONNECTION_REFUSED'):
                await isolated_page.goto('http://localhost:27182/non-existing-url')

        @sync
        async def test_fails_on_exceeding_nav_timeout(self, isolated_page, server):
            holder = server.app.one_time_request_delay(server.empty_page)
            with pytest.raises(TimeoutError, match=NAV_TIMEOUT_MATCH):
                await isolated_page.goto(server.empty_page, timeout=1)
            holder.set_result(None)

        @sync
        async def test_fails_on_exceeding_default_nav_timeout(self, isolated_page, server):
            holder = server.app.one_time_request_delay(server.empty_page)
            isolated_page.setDefaultNavigationTimeout(1)
            with pytest.raises(TimeoutError, match=NAV_TIMEOUT_MATCH):
                await isolated_page.goto(server.empty_page)
            holder.set_result(None)

        @sync
        async def test_fails_on_exceeding_default_timeout(self, isolated_page, server):
            holder = server.app.one_time_request_delay(server.empty_page)
            isolated_page.setDefaultTimeout(1)
            with pytest.raises(TimeoutError, match=NAV_TIMEOUT_MATCH):
                await isolated_page.goto(server.empty_page)
            holder.set_result(None)

        @sync
        async def test_prioritizes_nav_timeout_of_default(self, isolated_page, server):
            delayer = server.app.one_time_request_delay(server.empty_page)
            isolated_page.setDefaultTimeout(0)
            isolated_page.setDefaultNavigationTimeout(1)
            with pytest.raises(TimeoutError, match=NAV_TIMEOUT_MATCH):
                await isolated_page.goto(server.empty_page)
            delayer.set_result(None)

        @sync
        async def test_timeout_disabled_when_equal_to_0(self, isolated_page, server):
            loaded = False
            isolated_page.once('load', var_setter('loaded', True))
            await isolated_page.goto(server / 'grid.html', timeout=0, waitUntil='load')
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
        async def test_returns_last_response_in_redirect_chain(self, isolated_page, server):
            server.app.set_one_time_redirects(
                '/redirect/1.html', '/redirect/2.html' '/redirect/3.html', server.empty_page
            )
            resp = await isolated_page.goto(server / 'redirect/1.html')
            assert resp.ok
            assert resp.url == server.empty_page

        # @needs_server_side_implementation
        @sync
        async def test_wait_for_network_idle_for_nav_to_succeed(self, isolated_page, server, event_loop):
            # Hold on to a bunch of requests without answering.
            # response_futures = [event_loop.create_future() for _ in range(4)]
            def request_holder():
                to_resolve = asyncio.get_event_loop().create_future()

                async def resolver():
                    return await to_resolve

                return to_resolve, resolver

            holders = {}
            for char in 'abcd':
                holders[char], resolver = request_holder()
                server.app.add_pre_request_subscriber(f'/fetch-request-{char}.js', resolver, should_return=True)

            initial_fetch_resources_requested = asyncio.gather(
                *[server.app.waitForRequest(f'/fetch-request-{char}.js') for char in 'abc']
            )
            second_fetch_resource_requested = server.app.waitForRequest('/fetch-request-d.js')

            # Navigate to a page which loads immediately and then does a bunch of
            # requests via javascript's fetch method.
            nav_prom = asyncio.create_task(isolated_page.goto(server / 'networkidle.html', waitUntil='networkidle0'))
            nav_finished = False
            nav_prom.add_done_callback(var_setter('nav_finished', True))

            # wait for the page's load event
            await waitEvent(isolated_page, 'load')
            assert nav_finished is False

            # Wait for the initial three resources to be requested.
            await initial_fetch_resources_requested

            # expect navigation still to be not finished.
            assert nav_finished is False

            for char, holder in holders.items():
                # respond to all but the last request
                if char != 'd':
                    holder.set_exception(web.HTTPNotFound())

            await second_fetch_resource_requested
            assert nav_finished is False

            # respond to last request
            holders['d'].set_exception(web.HTTPNotFound())

            resp = await nav_prom
            # nav should succeed
            assert resp.ok

        @sync
        async def test_navs_to_dataURL_and_fires_dataURL_reqs(self, isolated_page, server):
            requests = []

            isolated_page.on('request', lambda r: requests.append(r) if not isFavicon(r) else None)
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
            resp = await isolated_page.goto(server.empty_page + '#hash')
            assert resp.status == 200
            assert resp.url == server.empty_page
            assert len(requests) == 1
            assert requests[0].url == server.empty_page

        @sync
        async def test_works_with_self_requesting_pages(self, isolated_page, server):
            resp = await isolated_page.goto(server / 'self-request.html')
            assert resp.status == 200
            assert 'self-request' in resp.url

        @sync
        async def test_shows_proper_error_msg_on_failed_nav(self, isolated_page, server):
            url = server.https / 'redirect/1.html'
            with pytest.raises(BrowserError, match=url):
                await isolated_page.goto(url)

        @sync
        async def test_sends_referer(self, isolated_page, server):
            req1, req2, *_ = await gather_with_timeout(
                server.app.waitForRequest('/grid.html'),
                server.app.waitForRequest('/digits/1.png'),
                isolated_page.goto(server / 'grid.html', referer='http://google.com/'),
            )
            assert req1.headers.get('referer') == 'http://google.com/'
            assert req2.headers.get('referer') == server / 'grid.html'

    class TestWaitForNavigation:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            resp, *_ = await gather_with_timeout(
                isolated_page.waitForNavigation(),
                isolated_page.evaluate('url => window.location.href = url', server / 'grid.html'),
            )
            assert resp.ok
            assert 'grid.html' in resp.url

        @sync
        @pytest.mark.skip()
        async def test_works_with_both_domcontentloaded_and_load(self, isolated_page, server, event_loop):

            continue_resp = server.app.one_time_request_delay(server / 'one-style.css')
            nav_promise = event_loop.create_task(isolated_page.goto(server / 'one-style.html'))
            domcontentloaded_task = event_loop.create_task(isolated_page.waitForNavigation())

            both_fired = False

            async def bothFired():
                await isolated_page.waitForNavigation(waitUntil=['load', 'domcontentloaded'])
                nonlocal both_fired
                both_fired = True

            both_fired_task = event_loop.create_task(bothFired())

            await server.app.waitForRequest('/one-style.css')
            await domcontentloaded_task

            assert both_fired is False
            continue_resp.set_result(None)
            await both_fired_task
            await nav_promise

        @sync
        async def test_works_with_clicking_anchor_urls(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.setContent('<a href="#foobar">foobar</a>')
            resp, *_ = await gather_with_timeout(isolated_page.waitForNavigation(), isolated_page.click('a'),)
            assert resp is None
            assert isolated_page.url == server.empty_page + '#foobar'

        @sync
        async def test_works_with_historypushState(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.setContent(
                '''
                <a onclick='javascript:pushState()'>SPA</a>
                <script>
                    function pushState() { history.pushState({}, '', 'wow.html') }
                </script>
            '''
            )
            resp, *_ = await gather_with_timeout(isolated_page.waitForNavigation(), isolated_page.click('a'),)
            assert resp is None
            assert isolated_page.url == server / '/wow.html'

        @sync
        async def test_works_with_historyreplaceState(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.setContent(
                '''
                <a onclick='javascript:pushState()'>SPA</a>
                <script>
                    function pushState() { history.replaceState({}, '', '/replaced.html') }
                </script>
            '''
            )
            resp, *_ = await gather_with_timeout(isolated_page.waitForNavigation(), isolated_page.click('a'),)
            assert resp is None
            assert isolated_page.url == server / 'replaced.html'

        @sync
        async def test_works_with_historyback_forward(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.setContent(
                '''
                <a id=back onclick='javascript:goBack()'>back</a>
                <a id=forward onclick='javascript:goForward()'>forward</a>
                <script>
                    function goBack() { history.back(); }
                    function goForward() { history.forward(); }
                    history.pushState({}, '', '/first.html');
                    history.pushState({}, '', '/second.html');
                </script>
            ''',
            )
            assert isolated_page.url == server / 'second.html'
            back_resp, *_ = await gather_with_timeout(isolated_page.waitForNavigation(), isolated_page.click('a#back'),)
            assert back_resp is None
            forward_resp, *_ = await gather_with_timeout(
                isolated_page.waitForNavigation(), isolated_page.click('a#forward'),
            )
            assert forward_resp is None
            assert isolated_page.url == server / 'second.html'

        @sync
        async def test_works_when_subframe_runs_windowstop(self, isolated_page, server):
            pass

    class TestGoBack:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.goto(server / 'grid.html')

            resp = await isolated_page.goBack()
            assert resp.ok
            assert server.empty_page in resp.url

            resp = await isolated_page.goForward()
            assert resp.ok
            assert 'grid.html' in resp.url

            resp = await isolated_page.goForward()
            assert resp is None

        @sync
        async def test_works_with_historyAPI(self, isolated_page, server):
            await isolated_page.goto(server.empty_page)
            await isolated_page.evaluate(
                '''() => {
                history.pushState({}, '', '/first.html');
                history.pushState({}, '', '/second.html');
            }'''
            )
            assert isolated_page.url == server / 'second.html'
            await isolated_page.goBack()
            assert isolated_page.url == server / 'first.html'
            await isolated_page.goBack()
            assert isolated_page.url == server.empty_page
            await isolated_page.goForward()
            assert isolated_page.url == server / 'first.html'

    @sync
    async def test_reload_works(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate('window._foo = 10')
        await isolated_page.reload()
        assert await isolated_page.evaluate('window._foo') is None


class TestFrame:
    class TestGoto:
        @sync
        async def test_navigates_subframes(self, isolated_page, server):
            await isolated_page.goto(server / 'frames/one-frame.html')
            assert 'one-frame.html' in isolated_page.frames[0].url
            assert 'frame.html' in isolated_page.frames[1].url

            resp = await isolated_page.frames[1].goto(server.empty_page)
            assert resp.ok
            assert resp.frame == isolated_page.frames[1]

        @sync
        async def test_rejects_when_frame_detaches(self, isolated_page, server, event_loop):
            await isolated_page.goto(server / 'frames/one-frame.html')

            frame_that_will_be_detached = isolated_page.frames[1]

            async def navigate_the_detaching_frame():
                await frame_that_will_be_detached.goto(server.empty_page)

            # this delays the response indefinately
            # the response from the server will be cancelled when the client disconnects
            # which it will because the frame is detached
            server.app.one_time_request_delay(server.empty_page)

            nav_task = event_loop.create_task(navigate_the_detaching_frame())

            await server.app.waitForRequest(server.empty_page)
            await isolated_page.Jeval('iframe', 'f => f.remove()')

            with pytest.raises(PageError, match='frame was detached'):
                await nav_task

        @sync
        async def test_returns_matching_responses(self, isolated_page, server):
            await isolated_page.setCacheEnabled(False)
            await isolated_page.goto(server.empty_page)

            frames = await gather_with_timeout(
                attachFrame(isolated_page, server.empty_page),
                attachFrame(isolated_page, server.empty_page),
                attachFrame(isolated_page, server.empty_page),
            )

            server_resps = ['aaa', 'bbb', 'ccc']
            navigations = []
            for resp, frame in zip(server_resps, frames):
                server.app.set_one_time_response('/one-style.html', resp.encode())
                _, nav = await asyncio.gather(
                    server.app.waitForRequest('/one-style.html'), frame.goto(server / 'one-style.html'),
                )

            for expected_resp, expected_frame, actual_resp in zip(server_resps, frames, navigations):
                assert actual_resp.frame == frames
                assert actual_resp.text == expected_resp

    class TestWaitForNavigation:
        @sync
        async def test_basic_usage(self, isolated_page, server):
            await isolated_page.goto(server / 'frames/one-frame.html')
            frame = isolated_page.frames[1]
            resp, *_ = await gather_with_timeout(
                frame.waitForNavigation(), frame.evaluate('url => window.location.href = url', server / 'grid.html')
            )
            assert resp.ok
            assert 'grid.html' in resp.url
            assert resp.frame == frame
            assert 'one-frame.html' in isolated_page.url

        @sync
        async def test_fails_when_frame_detaches(self, isolated_page, server, event_loop):
            # see corresponding Page test
            await isolated_page.goto(server / 'frames/one-frame.html')
            frame = isolated_page.frames[1]

            nav_task = event_loop.create_task(frame.waitForNavigation())

            await gather_with_timeout(
                server.app.waitForRequest(server.empty_page), isolated_page.Jeval('iframe', 'f => f.remove()'),
            )

            with pytest.raises(NetworkError, match='frame was detached') as excpt:
                await nav_task
