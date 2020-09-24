"""
Tests relating to headful mode
"""
import os
import platform
import pytest
import tempfile
import shutil

from pyppeteer import launch
from syncer import sync

EXTENSION_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "simple-extension")


class TestHeadful:
    @pytest.fixture
    def extension_options(self, default_browser_options):
        default_browser_options["headless"] = False
        default_browser_options["args"] += [
            '--disable-extensions-except=' + EXTENSION_PATH,
            '--load-extension=' + EXTENSION_PATH
        ]
        return default_browser_options

    @pytest.fixture
    def headful_options(self, default_browser_options):
        default_browser_options["headless"] = False
        return default_browser_options

    @sync
    async def test_background_page_target_type_should_be_available(self, extension_options):
        browser_with_extension = await launch(**extension_options)
        page = await browser_with_extension.newPage()
        background_page_target = await browser_with_extension.waitForTarget(lambda t: t.type == 'background_page')
        await page.close()
        await browser_with_extension.close()
        assert background_page_target is not None

    @sync
    async def test_target_page_should_return_a_background_page(self, extension_options):
        browser_with_extension = await launch(**extension_options)
        background_page_target = await browser_with_extension.waitForTarget(lambda t: t.type == 'background_page')
        page = await background_page_target.page()
        assert await page.evaluate('() => 2 * 3') == 6
        assert await page.evaluate('() => window.MAGIC') == 42
        await browser_with_extension.close()

    @sync
    async def test_should_have_default_url_when_launching_browser(self, extension_options):
        browser = await launch(**extension_options)
        pages = [page.url for page in await browser.pages]
        assert pages == ['about:blank']
        await browser.close()

    @sync
    async def test_headless_should_be_able_to_read_cookies_written_by_headful(self, default_browser_options, headful_options, server):
        user_data_dir = tempfile.mkdtemp(None, 'pptr_tmp_folder-')
        # Write cookie in headful mode
        headful_browser = await launch(**headful_options, userDataDir=user_data_dir)
        headful_page = await headful_browser.newPage()
        await headful_page.goto(server.empty_page)
        await headful_page.evaluate('() => document.cookie = "foo=true; expires=Fri, 31 Dec 9999 23:59:59 GMT"')
        await headful_browser.close()
        #  Read the cookie from headless chrome
        headless_browser = await launch(**default_browser_options, userDataDir=user_data_dir)
        headless_page = await headless_browser.newPage()
        await headless_page.goto(server.empty_page)
        cookie = await headless_page.evaluate('() => document.cookie')
        await headless_browser.close()
        shutil.rmtree(user_data_dir, True)
        assert cookie == 'foo=true'

    @sync
    async def test_should_close_browser_with_beforeunload_page(self, headful_options, server):
        browser = await launch(**headful_options)
        page = await browser.newPage()
        await page.goto(server.base + '/beforeunload.html')
        # We have to interact with a page so that 'beforeunload' handlers fire
        await page.click('body')
        await browser.close()

    # @pytest.mark.timeout(300)
    @sync
    async def test_should_open_devtools_when_devtools_true_option_is_given(self, headful_options):
        browser = await launch(**headful_options, devtools=True)
        context = await browser.createIncognitoBrowserContext()
        await context.newPage()
        target = context.targets()[1]
        assert 'devtools://' in target.url
        await context.close()
        await browser.close()

    @sync
    async def test_page_bringToFront_should_work(self, headful_options):
        browser = await launch(**headful_options)
        page1 = await browser.newPage()
        page2 = await browser.newPage()

        await page1.bringToFront()
        assert await page1.evaluate('() => document.visibilityState') == 'visible'
        assert await page2.evaluate('() => document.visibilityState') == 'hidden'

        await page2.bringToFront()
        assert await page1.evaluate('() => document.visibilityState') == 'hidden'
        assert await page2.evaluate('() => document.visibilityState') == 'visible'

        await page1.close()
        await page2.close()
        await browser.close()
