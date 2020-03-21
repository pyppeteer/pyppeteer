import pytest
from syncer import sync

from tests.utils import waitEvent


@sync
async def test_async_stacks(isolated_page):
    pass


class TestClose:
    @sync
    async def test_reject_all_pending_promises(self, isolated_page, event_loop):
        error = None
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
    pass


class TestEventError:
    pass


class TestEventsPopup:
    pass


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
