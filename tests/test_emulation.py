import pytest
from pyppeteer.device_descriptors import devices
from syncer import sync
from tests.conftest import chrome_only


class TestPageViewport:

    iPhone = devices['iPhone 6']
    iPhoneLandscape = devices['iPhone 6 landscape']

    @sync
    async def test_gets_viewport_size(self, isolated_page):
        """The page should get the proper viewport size"""
        page = isolated_page
        assert page.viewport == {"width": 800, "height": 600}
        await page.setViewport({"width": 123, "height": 456})
        assert page.viewport == {"width": 123, "height": 456}

    @sync
    async def test_supports_mobile_emulation(self, server, isolated_page):
        """The page should support mobile emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate("window.innerWidth") == 800
        await page.setViewport(self.iPhone["viewport"])
        assert await page.evaluate("window.innerWidth") == 375
        await page.setViewport({"width": 400, "height": 300})
        assert await page.evaluate("window.innerWidth") == 400

    @chrome_only
    @sync
    async def test_supports_touch(self, server, isolated_page):
        """Verify support of touch emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate("'ontouchstart' in window") == False
        await page.setViewport(self.iPhone["viewport"])
        assert await page.evaluate("'ontouchstart' in window") == True
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
        await page.setViewport({"width": 100, "height": 100})
        assert await page.evaluate("'ontouchstart' in window") == False

    @chrome_only
    @sync
    async def test_detects_touch(self, server, isolated_page):
        """It should detect touch when applying viewport with touches."""
        page = isolated_page
        await page.goto(server / 'detect-touch.html')
        assert await page.evaluate("document.body.textContent.trim()") == 'NO'
        await page.setViewport(self.iPhone['viewport'])
        await page.goto(server / 'detect-touch.html')
        assert await page.evaluate("document.body.textContent.trim()") == 'YES'

    @chrome_only
    @sync
    async def test_is_detecteable_by_modernizr(self, assets, isolated_page):
        """Verify the emulation should be detectable by Modernizr JS lib."""
        page = isolated_page
        await page.setViewport({"width": 800, "height": 600, "hasTouch": True})
        await page.addScriptTag(path=f"{assets / 'modernizr.js'}")
        assert await page.evaluate("Modernizr.touchevents") == True

    @chrome_only
    @sync
    async def test_supports_landscape_emulation(self, server, isolated_page):
        """Verify the page emulation should support landscape emulation."""
        page = isolated_page
        await page.goto(server / 'mobile.html')
        assert await page.evaluate("screen.orientation.type") == 'portrait-primary'
        await page.setViewport(self.iPhoneLandscape['viewport'])
        assert await page.evaluate("screen.orientation.type") == 'landscape-primary'
        await page.setViewport({"width": 100, "height": 100})
        assert await page.evaluate("screen.orientation.type") == 'portrait-primary'


"""
  describe('Page.emulate', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      await page.goto(server.PREFIX + '/mobile.html');
      await page.emulate(iPhone);
      expect(await page.evaluate(() => window.innerWidth)).toBe(375);
      expect(await page.evaluate(() => navigator.userAgent)).toContain(
        'iPhone'
      );
    });
    it('should support clicking', async () => {
      const { page, server } = getTestState();

      await page.emulate(iPhone);
      await page.goto(server.PREFIX + '/input/button.html');
      const button = await page.$('button');
      await page.evaluate(
        (button) => (button.style.marginTop = '200px'),
        button
      );
      await button.click();
      expect(await page.evaluate(() => result)).toBe('Clicked');
    });
  });

  describe('Page.emulateMedia [deprecated]', function () {
    /* emulateMedia is deprecated in favour of emulateMediaType but we
     * don't want to remove it from Puppeteer just yet. We can't check
     * that emulateMedia === emulateMediaType because when running tests
     * with COVERAGE=1 the methods get rewritten. So instead we
     * duplicate the tests for emulateMediaType and ensure they pass
     * when calling the deprecated emulateMedia method.
     *
     * If you update these tests, you should update emulateMediaType's
     * tests, and vice-versa.
     */
    itFailsFirefox('should work', async () => {
      const { page } = getTestState();

      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        true
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(
        false
      );
      await page.emulateMedia('print');
      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        false
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(true);
      await page.emulateMedia(null);
      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        true
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(
        false
      );
    });
    it('should throw in case of bad argument', async () => {
      const { page } = getTestState();

      let error = null;
      await page.emulateMedia('bad').catch((error_) => (error = error_));
      expect(error.message).toBe('Unsupported media type: bad');
    });
  });

  describe('Page.emulateMediaType', function () {
    /* NOTE! Updating these tests? Update the emulateMedia tests above
     * too (and see the big comment for why we have these duplicated).
     */
    itFailsFirefox('should work', async () => {
      const { page } = getTestState();

      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        true
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(
        false
      );
      await page.emulateMediaType('print');
      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        false
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(true);
      await page.emulateMediaType(null);
      expect(await page.evaluate(() => matchMedia('screen').matches)).toBe(
        true
      );
      expect(await page.evaluate(() => matchMedia('print').matches)).toBe(
        false
      );
    });
    it('should throw in case of bad argument', async () => {
      const { page } = getTestState();

      let error = null;
      await page.emulateMediaType('bad').catch((error_) => (error = error_));
      expect(error.message).toBe('Unsupported media type: bad');
    });
  });

  describe('Page.emulateMediaFeatures', function () {
    itFailsFirefox('should work', async () => {
      const { page } = getTestState();

      await page.emulateMediaFeatures([
        { name: 'prefers-reduced-motion', value: 'reduce' },
      ]);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: reduce)').matches
        )
      ).toBe(true);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: no-preference)').matches
        )
      ).toBe(false);
      await page.emulateMediaFeatures([
        { name: 'prefers-color-scheme', value: 'light' },
      ]);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: light)').matches
        )
      ).toBe(true);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: dark)').matches
        )
      ).toBe(false);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: no-preference)').matches
        )
      ).toBe(false);
      await page.emulateMediaFeatures([
        { name: 'prefers-color-scheme', value: 'dark' },
      ]);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: dark)').matches
        )
      ).toBe(true);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: light)').matches
        )
      ).toBe(false);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: no-preference)').matches
        )
      ).toBe(false);
      await page.emulateMediaFeatures([
        { name: 'prefers-reduced-motion', value: 'reduce' },
        { name: 'prefers-color-scheme', value: 'light' },
      ]);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: reduce)').matches
        )
      ).toBe(true);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: no-preference)').matches
        )
      ).toBe(false);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: light)').matches
        )
      ).toBe(true);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: dark)').matches
        )
      ).toBe(false);
      expect(
        await page.evaluate(
          () => matchMedia('(prefers-color-scheme: no-preference)').matches
        )
      ).toBe(false);
    });
    it('should throw in case of bad argument', async () => {
      const { page } = getTestState();

      let error = null;
      await page
        .emulateMediaFeatures([{ name: 'bad', value: '' }])
        .catch((error_) => (error = error_));
      expect(error.message).toBe('Unsupported media feature: bad');
    });
  });

  describeFailsFirefox('Page.emulateTimezone', function () {
    it('should work', async () => {
      const { page } = getTestState();

      page.evaluate(() => {
        globalThis.date = new Date(1479579154987);
      });
      await page.emulateTimezone('America/Jamaica');
      expect(await page.evaluate(() => date.toString())).toBe(
        'Sat Nov 19 2016 13:12:34 GMT-0500 (Eastern Standard Time)'
      );

      await page.emulateTimezone('Pacific/Honolulu');
      expect(await page.evaluate(() => date.toString())).toBe(
        'Sat Nov 19 2016 08:12:34 GMT-1000 (Hawaii-Aleutian Standard Time)'
      );

      await page.emulateTimezone('America/Buenos_Aires');
      expect(await page.evaluate(() => date.toString())).toBe(
        'Sat Nov 19 2016 15:12:34 GMT-0300 (Argentina Standard Time)'
      );

      await page.emulateTimezone('Europe/Berlin');
      expect(await page.evaluate(() => date.toString())).toBe(
        'Sat Nov 19 2016 19:12:34 GMT+0100 (Central European Standard Time)'
      );
    });

    it('should throw for invalid timezone IDs', async () => {
      const { page } = getTestState();

      let error = null;
      await page.emulateTimezone('Foo/Bar').catch((error_) => (error = error_));
      expect(error.message).toBe('Invalid timezone ID: Foo/Bar');
      await page.emulateTimezone('Baz/Qux').catch((error_) => (error = error_));
      expect(error.message).toBe('Invalid timezone ID: Baz/Qux');
    });
  });
});
"""
