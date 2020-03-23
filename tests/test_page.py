import asyncio
from contextlib import suppress

import pytest
from syncer import sync

from pyppeteer.errors import PageError
from tests.utils import waitEvent, gather_with_timeout


@sync
async def test_async_stacks(isolated_page, server_url_empty_page):
    with pytest.raises(Exception) as excpt:
        await isolated_page.goto(server_url_empty_page)
        assert __file__ in str(excpt)


class TestClose:
    @sync
    async def test_reject_all_pending_promises(self, isolated_page, event_loop):
        fut = event_loop.create_task(isolated_page.evaluate('()=>new Promise(resolve=>{})'))
        await isolated_page.close()
        with pytest.raises(Exception) as excpt:
            await fut
        assert 'Protocol error' in str(excpt)

    @sync
    async def test_closed_page_removed_from_pages_prop(self, isolated_page, shared_browser):
        assert isolated_page in await shared_browser.pages
        await isolated_page.close()
        assert isolated_page not in await shared_browser.pages

    @sync
    async def test_run_beforeunload(self, isolated_page, server_url, firefox):
        await isolated_page.goto(server_url + '/beforeunload.html')
        # interact w/ page so beforeunload handler fires
        await isolated_page.click('body')
        page_closing_fut = isolated_page._loop.create_task(isolated_page.close(runBeforeUnload=True))
        dialog = await waitEvent(isolated_page, 'dialog')
        assert dialog.type == 'beforeunload'
        assert dialog.defaultValue == ''
        if not firefox:
            assert dialog.message == ''
        elif firefox:
            assert (
                dialog.message
                == 'This page is asking you to confirm that you want to leave - data you have entered may not be saved.'
            )
        await dialog.accept()
        await page_closing_fut

    @sync
    async def test_not_run_beforeunload_by_default(self, isolated_page, server_url):
        await isolated_page.goto(server_url + '/beforeunload.html')
        # interact w/ page so beforeunload handler fires
        await isolated_page.click('body')
        # if beforeunload handlers are fired, this will timeout as a dialog will block the close of the page
        await isolated_page.close()

    @sync
    async def test_set_page_close_state(self, isolated_page, server_url):
        assert isolated_page.isClosed is False
        await isolated_page.close()
        assert isolated_page.isClosed


class TestEventsLoad:
    @sync
    async def test_load_event_fired(self, isolated_page):
        event = waitEvent(isolated_page, 'load')
        done, _ = await asyncio.wait((isolated_page.goto('about:blank'), event), timeout=5)
        assert len(done) == 2


class TestEventError:
    @sync
    async def test_raises_on_page_crash(self, event_loop, isolated_page):
        error = waitEvent(isolated_page, 'error')
        with suppress(asyncio.TimeoutError):
            await isolated_page.goto('chrome://crash', timeout=2_000)
        assert str(await error) == 'Page crashed!'


class TestEventsPopup:
    @sync
    async def test_popup_props(self, isolated_page):
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'), isolated_page.evaluate('() => window.open("about:blank")'),
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener')

    @sync
    async def test_popup_noopener(self, isolated_page):
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'),
            isolated_page.evaluate('() => window.open("about:blank", null, "noopener")'),
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False

    @sync
    async def test_clicking_target_blank(self, isolated_page, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        await isolated_page.setContent('<a target=_blank href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(waitEvent(isolated_page, 'popup'), isolated_page.click('a'),)
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener')

    @sync
    async def test_fake_clicking_target_and_noopener(self, isolated_page, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        await isolated_page.setContent('<a target=_blank rel=noopener href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(waitEvent(isolated_page, 'popup'), isolated_page.click('a'))
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False


class TestBrowserContextOverridePermissions:
    @staticmethod
    def get_permission_state(page, name):
        return page.evaluate('name => navigator.permissions.query({name}).then(result => result.state)', name)

    @sync
    async def test_prompt_by_default(self, isolated_page, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'prompt'

    @sync
    async def test_deny_unlisted_permission(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        await isolated_context.overridePermissions(server_url_empty_page, [])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'denied'

    @sync
    async def test_fail_on_bad_permission(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        with pytest.raises(RuntimeError) as excpt:
            await isolated_context.overridePermissions(server_url_empty_page, ['foo'])
        assert 'Unknown permission: foo' in str(excpt)

    @sync
    async def test_grant_permission_when_overridden(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_context.overridePermissions(server_url_empty_page, ['geolocation'])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'granted'

    @sync
    async def test_reset_permissions(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_context.overridePermissions(server_url_empty_page, ['geolocation'])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'granted'
        await isolated_context.clearPermissionOverrides()
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'prompt'

    @sync
    async def test_permission_onchange_fired(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_page.goto(server_url_empty_page)
        await isolated_page.evaluate(
            """
        () => {
            window.events = [];
            return navigator.permissions.query({name: 'geolocation'}).then(function(result) {
                window.events.push(result.state);
                result.onchange = function() {
                    window.events.push(result.state);
                };
            });
        }
        """
        )
        assert await isolated_page.evaluate('() => window.events') == ['prompt']
        await isolated_context.overridePermissions(server_url_empty_page, [])
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied']
        await isolated_context.overridePermissions(server_url_empty_page, ['geolocation'])
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied', 'granted']
        await isolated_context.clearPermissionOverrides()
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied', 'granted', 'prompt']


class TestSetGeolocation:
    @sync
    async def test_set_geolocation(self, isolated_page, isolated_context, server_url_empty_page):
        await isolated_context.overridePermissions(server_url_empty_page, ['geolocation'])
        await isolated_page.goto(server_url_empty_page)
        await isolated_page.setGeolocation(longitude=10, latitude=10)
        geolocation = await isolated_page.evaluate(
            """
        () => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
            resolve({latitude: position.coords.latitude, longitude: position.coords.longitude});
        }))
        """
        )
        assert geolocation == {'longitude': 10, 'latitude': 10}

    @sync
    async def test_rejects_invalid_lat_long(self, isolated_page):
        with pytest.raises(PageError):
            await isolated_page.setGeolocation(longitude=200, latitude=10)
        with pytest.raises(PageError):
            await isolated_page.setGeolocation(longitude=90, latitude=200)


class TestSetOfflineMode:
    @sync
    async def test_set_offline_mode(self, isolated_page, server_url_empty_page):
        await isolated_page.setOfflineMode(True)
        with pytest.raises(PageError):
            await isolated_page.goto(server_url_empty_page)
        await isolated_page.setOfflineMode(False)
        resp = await isolated_page.reload()
        assert resp.status == 200

    @sync
    async def test_emulate_navigator_online(self, isolated_page):
        def nav_online():
            return isolated_page.evaluate('() => window.navigator.onLine')

        assert await nav_online()
        await isolated_page.setOfflineMode(True)
        assert await nav_online() is False
        await isolated_page.setOfflineMode(False)
        assert await nav_online()


class TestExecutionContextQueryObjects:
    @sync
    async def test_queries_objects(self, isolated_page):
        await isolated_page.evaluate('() => window.set = new Set(["hello", "world"])')
        proto_handle = await isolated_page.evaluateHandle('() => Set.prototype')
        objs_handle = await isolated_page.queryObjects(proto_handle)
        # todo (Mattwmaster58): correct typing
        assert len(await isolated_page.evaluate('objects => objects.length', objs_handle)) == 1
        assert await isolated_page.evaluate('objects => Array.from(objects[0].values())', objs_handle) == [
            'hello',
            'world',
        ]

    @sync
    async def test_queries_objects_non_blank_page(self, isolated_page, server_url_blank_page):
        await isolated_page.goto(server_url_blank_page)
        await isolated_page.evaluate('() => window.set = new Set(["hello", "world"])')
        proto_handle = await isolated_page.evaluateHandle('() => Set.prototype')
        objs_handle = await isolated_page.queryObjects(proto_handle)
        # todo (Mattwmaster58): correct typing
        assert len(await isolated_page.evaluate('objects => objects.length', objs_handle)) == 1
        assert await isolated_page.evaluate('objects => Array.from(objects[0].values())', objs_handle) == [
            'hello',
            'world',
        ]

    @sync
    async def test_fails_on_disposed_handles(self, isolated_page):
        proto_handle = await isolated_page.evaluateHandle('() => HTMLBodyElement.prototype')
        await proto_handle.dispose()
        with pytest.raises(PageError) as excpt:
            await isolated_page.queryObjects(proto_handle)
        assert 'Prototype JSHandle is disposed!' in str(excpt)

    @sync
    async def test_fail_on_primitive_vals_as_proto(self, isolated_page):
        proto_handle = await isolated_page.evaluateHandle('() => 42')
        with pytest.raises(PageError) as excpt:
            await isolated_page.queryObjects(proto_handle)
        assert 'Prototype JSHandle must not be referencing primitive value' in str(excpt)




class TestEventsConsole:
    pass


class TestEventsDOMContentLoaded:
    pass


class TestMetrics:
    pass


class TestWaitForRequest:
    pass


class TestWaitForResponse:
    pass


class TestExposeFunction:
    pass


class TestEventsPageError:
    pass


class TestSetUserAgent:
    pass


class TestSetContent:
    pass


class TestSetBypassCSP:
    pass


class TestAddScriptTag:
    pass


class TestAddStyleTag:
    pass


class TestURL:
    pass


class TestSetJSEnabled:
    pass


class TestSetCacheEnabled:
    pass


class TestTitle:
    pass


class TestEventsClose:
    pass


class TestBrowser:
    pass


class TestBrowserContext:
    pass
