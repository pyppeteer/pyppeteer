import pytest
from syncer import sync


@sync
async def test_async_stacks(isolated_page):
    pass


class TestClose:
    @sync
    async def test_reject_all_pending_promises(self, isolated_context):
        page = await isolated_context.newPage()
        error = None
        fut = page._loop.create_task(page.evaluate('()=>new Promise(resolve=>{})'))
        await page.close()
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
    async def test_(self, isolated_context, ):


        


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
