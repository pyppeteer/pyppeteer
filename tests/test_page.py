import asyncio
from contextlib import suppress

import pytest
from syncer import sync

from tests.utils import waitEvent, gather_with_timeout


@sync
async def test_async_stacks(isolated_page, server_url):
    with pytest.raises(Exception) as excpt:
        await isolated_page.goto(server_url + '/empty.html')
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
    async def test_closed_page_removed_from_pages_prop(self, shared_browser):
        page = await shared_browser.newPage()
        assert page in await shared_browser.pages
        await page.close()
        assert page not in await shared_browser.pages

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
    async def test_set_page_close_state(self, isolated_context, server_url):
        page = await isolated_context.newPage()
        assert page.isClosed is False
        await page.close()
        assert page.isClosed


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
            waitEvent(isolated_page, 'popup'),
            isolated_page.evaluate('() => window.open("about:blank")'),
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
    async def test_clicking_target_blank(self, isolated_page, server_url):
        await isolated_page.goto(server_url + '/empty.html')
        await isolated_page.setContent('<a target=_blank href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'),
            isolated_page.click('a'),
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener')

    @sync
    async def test_fake_clicking_target_and_noopener(self, isolated_page, server_url):
        await isolated_page.goto(server_url + '/empty.html')
        await isolated_page.setContent('<a target=_blank rel=noopener href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'),
            isolated_page.Jeval('a', 'elem => elem.click()')
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False

    @sync
    async def test_clicking_target_blank_and_noopener(self, isolated_page, server_url):
        await isolated_page.goto(server_url + '/empty.html')
        await isolated_page.setContent('<a target=_blank rel=noopener href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'),
            isolated_page.click('a')
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False




class TestBrowserContextOverridePermissions:
    pass


class TestSetGeolocation:
    pass


class TestSetOfflineMode:
    pass


class TestExecutionContextQueryObjects:
    pass


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
