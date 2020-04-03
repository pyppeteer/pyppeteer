"""
Tests relating to page/frame navigation
"""
import pytest
from syncer import sync

from pyppeteer.errors import BrowserError


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
        @pytest.mark.skip(reason='Needs server side implementation')
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
        @pytest.mark.skip(reason='Needs server side implementation')
        async def test_works_with_204_subframes(self, isolated_page, server):
            pass

        @sync
        @pytest.mark.skip(reason='Needs server side implementation')
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
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto('yeet')
            assert 'invalid url' in str(excpt).lower()

        @sync
        async def test_fails_on_bad_ss(self, isolated_page, server):
            # Make sure that network events do not emit 'undefined'.
            # @see https://crbug.com/750469
            def assert_truthy(o):
                assert o

            isolated_page.on('request', assert_truthy)
            isolated_page.on('requestfinished', assert_truthy)
            isolated_page.on('requestfailed', assert_truthy)
            with pytest.raises(BrowserError) as excpt:
                await isolated_page.goto(server.https.empty_page)
            assert 'ERR_CERT_AUTHORITY_INVALID' in str(excpt) or 'SSL_ERROR_UNKNOWN' in str(excpt)

        @sync
        @pytest.mark.skip(reason='Needs server side implementation')
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

    class TestWaitForNavigation:
        pass

    class TestGoBack:
        pass

    class TestReload:
        pass


class Frame:
    class TestGoto:
        pass

    class TestWaitForNavigation:
        pass
