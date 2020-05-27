import pytest
from pyppeteer.device_descriptors import devices
from pyppeteer.errors import BrowserError, PageError
from syncer import sync
from tests.conftest import chrome_only

iPhone = devices['iPhone 6']
iPhoneLandscape = devices['iPhone 6 landscape']


class TestPageViewport:
    @sync
    async def test_gets_viewport_size(self, isolated_page):
        """The page should get the proper viewport size"""
        page = isolated_page
        assert page.viewport == {'width': 800, 'height': 600}
        await page.setViewport({'width': 123, 'height': 456})
        assert page.viewport == {'width': 123, 'height': 456}

    @sync
    async def test_supports_mobile_emulation(self, server, isolated_page):
        """The page should support mobile emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate('window.innerWidth') == 800
        await page.setViewport(iPhone['viewport'])
        assert await page.evaluate('window.innerWidth') == 375
        await page.setViewport({'width': 400, 'height': 300})
        assert await page.evaluate('window.innerWidth') == 400

    @chrome_only
    @sync
    async def test_supports_touch(self, server, isolated_page):
        """Verify support of touch emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate('"ontouchstart" in window') is False
        await page.setViewport(iPhone['viewport'])
        assert await page.evaluate('"ontouchstart" in window') is True
        dispatchTouch = """() => {
                let fulfill;
                const promise = new Promise((x) => (fulfill = x));
                window.ontouchstart = function (e) {
                  fulfill('Received touch');
                };
                window.dispatchEvent(new Event('touchstart'));

                fulfill('Did not receive touch');

                return promise;
            }
        """
        assert await page.evaluate(dispatchTouch) == 'Received touch'
        await page.setViewport({'width': 100, 'height': 100})
        assert await page.evaluate('"ontouchstart" in window') is False

    @chrome_only
    @sync
    async def test_detects_touch(self, server, isolated_page):
        """It should detect touch when applying viewport with touches."""
        page = isolated_page
        await page.goto(server / 'detect-touch.html')
        assert await page.evaluate('document.body.textContent.trim()') == 'NO'
        await page.setViewport(iPhone['viewport'])
        assert await page.evaluate('document.body.textContent.trim()') == 'YES'

    @chrome_only
    @sync
    async def test_is_detecteable_by_modernizr(self, server, isolated_page):
        """Verify the emulation should be detectable by Modernizr JS lib."""
        page = isolated_page
        await page.setViewport({'width': 800, 'height': 600, 'hasTouch': True})
        await page.addScriptTag(url=server / 'modernizr.js')
        assert await page.evaluate('Modernizr.touchevents') is True

    @chrome_only
    @sync
    async def test_supports_landscape_emulation(self, server, isolated_page):
        """It should support landscape emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate('screen.orientation.type') == 'portrait-primary'
        await page.setViewport(iPhoneLandscape['viewport'])
        assert await page.evaluate('screen.orientation.type') == 'landscape-primary'
        await page.setViewport({'width': 100, 'height': 100})
        assert await page.evaluate('screen.orientation.type') == 'portrait-primary'


class TestPageEmulation:
    @sync
    async def test_page_emulates_mobile_devices(self, server, isolated_page):
        """Verify the page emulation works with emulating mobile devices."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        await page.emulate(viewport=iPhone['viewport'], userAgent=iPhone['userAgent'])
        assert await page.evaluate('window.innerWidth') == 375
        assert 'iPhone' in await page.evaluate('navigator.userAgent')

    @sync
    async def test_supports_clicking(self, server, isolated_page):
        """Verify the emulation should support clicking."""
        page = isolated_page
        await page.emulate(viewport=iPhone['viewport'], userAgent=iPhone['userAgent'])
        await page.goto(server / 'input/button.html')
        button = await page.J('button')
        await page.evaluate('button => button.style.marginTop = "200px"', button)
        await button.click()
        assert await page.evaluate('result') == 'Clicked'


class TestEmulateMediaType:

    @chrome_only
    @sync
    async def test_emulation_media_type(self, isolated_page):
        """The emulation media type should work."""
        page = isolated_page
        assert await page.evaluate('matchMedia("screen").matches') is True
        assert await page.evaluate('matchMedia("print").matches') is False
        await page.emulateMediaType('print')
        assert await page.evaluate('matchMedia("screen").matches') is False
        assert await page.evaluate('matchMedia("print").matches') is True
        await page.emulateMediaType(None)
        assert await page.evaluate('matchMedia("screen").matches') is True
        assert await page.evaluate('matchMedia("print").matches') is False

    @chrome_only
    @sync
    async def test_emulation_media(self, isolated_page):
        """The `emulationMedia()` is a deprecated alias for `emulationMediaType()`."""
        page = isolated_page
        assert await page.evaluate('matchMedia("screen").matches') is True
        assert await page.evaluate('matchMedia("print").matches') is False
        await page.emulateMedia('print')
        assert await page.evaluate('matchMedia("screen").matches') is False
        assert await page.evaluate('matchMedia("print").matches') is True
        await page.emulateMedia(None)
        assert await page.evaluate('matchMedia("screen").matches') is True
        assert await page.evaluate('matchMedia("print").matches') is False

    @sync
    async def test_throws_err_if_bad_arg(self, isolated_page):
        """Exception should be thrown in case of bad argument"""
        page = isolated_page
        with pytest.raises(ValueError, match="Unsupported media type: bad"):
            await page.emulateMediaType('bad')


class TestEmulateMediaFeatures:
    @chrome_only
    @sync
    async def test_emulate_media_features_work(self, isolated_page):
        """The emulate media features work."""
        page = isolated_page
        await page.emulateMediaFeatures([{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        assert await page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") is True
        assert await page.evaluate("matchMedia('(prefers-reduced-motion: no-preference)').matches") is False
        await page.emulateMediaFeatures([{'name': 'prefers-color-scheme', 'value': 'light'}])
        assert await page.evaluate("matchMedia('(prefers-color-scheme: light)').matches") is True
        assert await page.evaluate("matchMedia('(prefers-color-scheme: dark)').matches") is False
        assert await page.evaluate("matchMedia('(prefers-color-scheme: no-preference)').matches") is False
        await page.emulateMediaFeatures([{'name': 'prefers-color-scheme', 'value': 'dark'}])
        assert await page.evaluate("matchMedia('(prefers-color-scheme: dark)').matches") is True
        assert await page.evaluate("matchMedia('(prefers-color-scheme: light)').matches") is False
        assert await page.evaluate("matchMedia('(prefers-color-scheme: no-preference)').matches") is False
        await page.emulateMediaFeatures(
            [{'name': 'prefers-reduced-motion', 'value': 'reduce'}, {'name': 'prefers-color-scheme', 'value': 'light'}]
        )
        assert await page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") is True
        assert await page.evaluate("matchMedia('(prefers-reduced-motion: no-preference)').matches") is False
        assert await page.evaluate("matchMedia('(prefers-color-scheme: light)').matches") is True
        assert await page.evaluate("matchMedia('(prefers-color-scheme: dark)').matches") is False
        assert await page.evaluate("matchMedia('(prefers-color-scheme: no-preference)').matches") is False

    @sync
    async def test_throws_err_if_bad_arg(self, isolated_page):
        """Exception should be thrown in case of bad argument"""
        page = isolated_page
        with pytest.raises(BrowserError, match="Unsupported media feature: {'name': 'bad', 'value': ''}"):
            await page.emulateMediaFeatures([{'name': 'bad', 'value': ''}])


class TestEmulateTimezone:
    @sync
    async def test_emulate_timezone_works(self, isolated_page):
        """Verify emulation of timezone works."""
        page = isolated_page
        await page.evaluate('globalThis.date = new Date(1479579154987)')
        await page.emulateTimezone('America/Jamaica')
        assert await page.evaluate('date.toString()') == 'Sat Nov 19 2016 13:12:34 GMT-0500 (Eastern Standard Time)'
        await page.emulateTimezone('Pacific/Honolulu')
        assert (
            await page.evaluate('date.toString()')
            == 'Sat Nov 19 2016 08:12:34 GMT-1000 (Hawaii-Aleutian Standard Time)'
        )
        await page.emulateTimezone('America/Buenos_Aires')
        assert await page.evaluate('date.toString()') == 'Sat Nov 19 2016 15:12:34 GMT-0300 (Argentina Standard Time)'
        await page.emulateTimezone('Europe/Berlin')
        assert (
            await page.evaluate('date.toString()')
            == 'Sat Nov 19 2016 19:12:34 GMT+0100 (Central European Standard Time)'
        )

    @sync
    async def test_err_thrown_if_invalid_timezone_ids(self, isolated_page):
        """The exceptions should be thrown for invalid timezone IDs."""
        page = isolated_page
        with pytest.raises(PageError, match='Invalid timezone ID: Foo/Bar'):
            await page.emulateTimezone('Foo/Bar')
        with pytest.raises(PageError, match='Invalid timezone ID: Baz/Qux'):
            await page.emulateTimezone('Baz/Qux')
