# -*- coding: utf-8 -*-
"""
Test Pyppeteer Network functionality.

"""

from syncer import sync

from tests.conftest import chrome_only
from tests import utils


def listener(request_container, request):
    """Save a request if the request's url doesn't contain a favicon url."""
    if not utils.isFavicon(request):
        request_container.append(request)


class TestPageEventsRequest:

    @sync
    async def test_fires_for_nav_requests(self, server, isolated_page):
        """The page event should be fired for navigation requests."""
        page = isolated_page
        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.goto(server.empty_page)
        assert len(requests) == 1

    @sync
    @chrome_only
    async def test_fires_for_iframes(self, server, isolated_page):
        """The page event should be fired for iframes."""
        page = isolated_page
        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.goto(server.empty_page)
        await utils.attachFrame(page, 'frame1', server.empty_page)
        assert len(requests) == 2

    @sync
    async def test_fires_for_fetches(self, server, isolated_page):
        """The page event should be fired for fetches."""
        page = isolated_page
        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.goto(server.empty_page)
        await page.evaluate("fetch('/empty.html')")
        assert len(requests) == 2


class TestRequestFrame:

    @sync
    async def test_works_for_main_frame_nav_request(self, server, isolated_page):
        """Request frame should work for main frame navigation request."""
        page = isolated_page
        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.goto(server.empty_page)
        assert len(requests) == 1
        assert requests[0].frame == page.mainFrame

    @sync
    @chrome_only
    async def test_works_for_subframe_nav_request(self, server, isolated_page):
        """Request frame should work for subframe navigation request."""
        page = isolated_page
        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.goto(server.empty_page)
        await utils.attachFrame(page, 'frame1', server.empty_page)
        assert len(requests) == 2
        assert requests[0].frame == page.frames[0]

    @sync
    @chrome_only
    async def test_works_for_fetch_requests(self, server, isolated_page):
        """Request frame should work for fetch requests."""
        page = isolated_page
        await page.goto(server.empty_page)

        requests = []
        page.on('request', lambda request: listener(requests, request))
        await page.evaluate("fetch('/digits/1.png')")
        assert len(requests) == 1
        assert requests[0].frame == page.mainFrame


class TestRequestHeader:

    @sync
    @chrome_only
    async def test_header_contains_user_agent(self, server, isolated_page):
        """Verify request contains a info about user agent in header."""
        page = isolated_page
        response = await page.goto(server.empty_page)
        assert 'Chrome' in response.request.headers['user-agent']


class TestResponseHeader:

    @sync
    @chrome_only
    async def test_header_contains_info(self, server, isolated_page):
        """Verify response header contains expected info."""
        page = isolated_page
        server.app.set_one_time_response(server.empty_page, b"headers={'foo': 'bar'}")
        response = await page.goto(server.empty_page)
        assert response.headers['foo'] == 'bar'


class TestResponseFromCache:

    @sync
    @chrome_only
    async def test_returns_false_for_non_cached(self, server, isolated_page):
        """Verify response `fromCache` property should return False for non-cached content."""
        page = isolated_page
        response = await page.goto(server.empty_page)
        assert not response.fromCache

    @sync
    @chrome_only
    async def test_returns_true_for_cached(self, server, isolated_page):
        """Verify response `fromCache` property should return True for cached content."""
        def listener_(request):
            if not utils.isFavicon(request):
                key = request.url.split("/").pop()
                responses[key] = request

        page = isolated_page
        responses = {}
        page.on('response', listener_)
        # Load and re-load to make sure it's cached.
        await page.goto(server / '/cached/one-style.html')
        await page.reload()
        assert len(responses) == 2
        assert responses.get('one-style.css').status == 200
        assert responses.get('one-style.css').fromCache
        assert responses.get('one-style.html').status == 304
        assert responses.get('one-style.html').fromCache is False


class TestResponseFromServiceWorker:

    @sync
    @chrome_only
    async def test_returns_false_for_non_service_worker(self, server, isolated_page):
        """Verify it should return False for non-service-worker content."""
        page = isolated_page
        response = await page.goto(server.empty_page)
        assert response.fromServiceWorker is False

    @sync
    @chrome_only
    async def test_returns_true_for_service_worker(self, server, isolated_page):
        """Verify it should return True for service-worker content."""

        def listener_(request):
            key = request.url.split("/").pop()
            responses[key] = request

        page = isolated_page
        responses = {}
        page.on('response', listener_)
        # Load and re-load to make sure serviceworker is installed and running.
        await page.goto(server / '/serviceworkers/fetch/sw.html', waitUntil='networkidle2')
        await page.evaluate('async () => await window.activationPromise')
        await page.reload()
        assert len(responses) == 2
        assert responses.get('sw.html').status == 200
        assert responses.get('sw.html').fromServiceWorker
        assert responses.get('style.css').status == 200
        assert responses.get('style.css').fromServiceWorker
"""

  describeFailsFirefox('Request.postData', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      await page.goto(server.EMPTY_PAGE);
      server.setRoute('/post', (req, res) => res.end());
      let request = null;
      page.on('request', (r) => (request = r));
      await page.evaluate(() =>
        fetch('./post', {
          method: 'POST',
          body: JSON.stringify({ foo: 'bar' }),
        })
      );
      expect(request).toBeTruthy();
      expect(request.postData()).toBe('{"foo":"bar"}');
    });
    it('should be |undefined| when there is no post data', async () => {
      const { page, server } = getTestState();

      const response = await page.goto(server.EMPTY_PAGE);
      expect(response.request().postData()).toBe(undefined);
    });
  });

  describeFailsFirefox('Response.text', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      const response = await page.goto(server.PREFIX + '/simple.json');
      const responseText = (await response.text()).trimEnd();
      expect(responseText).toBe('{"foo": "bar"}');
    });
    it('should return uncompressed text', async () => {
      const { page, server } = getTestState();

      server.enableGzip('/simple.json');
      const response = await page.goto(server.PREFIX + '/simple.json');
      expect(response.headers()['content-encoding']).toBe('gzip');
      const responseText = (await response.text()).trimEnd();
      expect(responseText).toBe('{"foo": "bar"}');
    });
    it('should throw when requesting body of redirected response', async () => {
      const { page, server } = getTestState();

      server.setRedirect('/foo.html', '/empty.html');
      const response = await page.goto(server.PREFIX + '/foo.html');
      const redirectChain = response.request().redirectChain();
      expect(redirectChain.length).toBe(1);
      const redirected = redirectChain[0].response();
      expect(redirected.status()).toBe(302);
      let error = null;
      await redirected.text().catch((error_) => (error = error_));
      expect(error.message).toContain(
        'Response body is unavailable for redirect responses'
      );
    });
    it('should wait until response completes', async () => {
      const { page, server } = getTestState();

      await page.goto(server.EMPTY_PAGE);
      // Setup server to trap request.
      let serverResponse = null;
      server.setRoute('/get', (req, res) => {
        serverResponse = res;
        // In Firefox, |fetch| will be hanging until it receives |Content-Type| header
        // from server.
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        res.write('hello ');
      });
      // Setup page to trap response.
      let requestFinished = false;
      page.on(
        'requestfinished',
        (r) => (requestFinished = requestFinished || r.url().includes('/get'))
      );
      // send request and wait for server response
      const [pageResponse] = await Promise.all([
        page.waitForResponse((r) => !utils.isFavicon(r.request())),
        page.evaluate(() => fetch('./get', { method: 'GET' })),
        server.waitForRequest('/get'),
      ]);

      expect(serverResponse).toBeTruthy();
      expect(pageResponse).toBeTruthy();
      expect(pageResponse.status()).toBe(200);
      expect(requestFinished).toBe(false);

      const responseText = pageResponse.text();
      // Write part of the response and wait for it to be flushed.
      await new Promise((x) => serverResponse.write('wor', x));
      // Finish response.
      await new Promise((x) => serverResponse.end('ld!', x));
      expect(await responseText).toBe('hello world!');
    });
  });

  describeFailsFirefox('Response.json', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      const response = await page.goto(server.PREFIX + '/simple.json');
      expect(await response.json()).toEqual({ foo: 'bar' });
    });
  });

  describeFailsFirefox('Response.buffer', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      const response = await page.goto(server.PREFIX + '/pptr.png');
      const imageBuffer = fs.readFileSync(
        path.join(__dirname, 'assets', 'pptr.png')
      );
      const responseBuffer = await response.buffer();
      expect(responseBuffer.equals(imageBuffer)).toBe(true);
    });
    it('should work with compression', async () => {
      const { page, server } = getTestState();

      server.enableGzip('/pptr.png');
      const response = await page.goto(server.PREFIX + '/pptr.png');
      const imageBuffer = fs.readFileSync(
        path.join(__dirname, 'assets', 'pptr.png')
      );
      const responseBuffer = await response.buffer();
      expect(responseBuffer.equals(imageBuffer)).toBe(true);
    });
  });

  describeFailsFirefox('Response.statusText', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      server.setRoute('/cool', (req, res) => {
        res.writeHead(200, 'cool!');
        res.end();
      });
      const response = await page.goto(server.PREFIX + '/cool');
      expect(response.statusText()).toBe('cool!');
    });
  });

  describeFailsFirefox('Network Events', function () {
    it('Page.Events.Request', async () => {
      const { page, server } = getTestState();

      const requests = [];
      page.on('request', (request) => requests.push(request));
      await page.goto(server.EMPTY_PAGE);
      expect(requests.length).toBe(1);
      expect(requests[0].url()).toBe(server.EMPTY_PAGE);
      expect(requests[0].resourceType()).toBe('document');
      expect(requests[0].method()).toBe('GET');
      expect(requests[0].response()).toBeTruthy();
      expect(requests[0].frame() === page.mainFrame()).toBe(true);
      expect(requests[0].frame().url()).toBe(server.EMPTY_PAGE);
    });
    it('Page.Events.Response', async () => {
      const { page, server } = getTestState();

      const responses = [];
      page.on('response', (response) => responses.push(response));
      await page.goto(server.EMPTY_PAGE);
      expect(responses.length).toBe(1);
      expect(responses[0].url()).toBe(server.EMPTY_PAGE);
      expect(responses[0].status()).toBe(200);
      expect(responses[0].ok()).toBe(true);
      expect(responses[0].request()).toBeTruthy();
      const remoteAddress = responses[0].remoteAddress();
      // Either IPv6 or IPv4, depending on environment.
      expect(
        remoteAddress.ip.includes('::1') || remoteAddress.ip === '127.0.0.1'
      ).toBe(true);
      expect(remoteAddress.port).toBe(server.PORT);
    });

    it('Page.Events.RequestFailed', async () => {
      const { page, server, isChrome } = getTestState();

      await page.setRequestInterception(true);
      page.on('request', (request) => {
        if (request.url().endsWith('css')) request.abort();
        else request.continue();
      });
      const failedRequests = [];
      page.on('requestfailed', (request) => failedRequests.push(request));
      await page.goto(server.PREFIX + '/one-style.html');
      expect(failedRequests.length).toBe(1);
      expect(failedRequests[0].url()).toContain('one-style.css');
      expect(failedRequests[0].response()).toBe(null);
      expect(failedRequests[0].resourceType()).toBe('stylesheet');
      if (isChrome)
        expect(failedRequests[0].failure().errorText).toBe('net::ERR_FAILED');
      else
        expect(failedRequests[0].failure().errorText).toBe('NS_ERROR_FAILURE');
      expect(failedRequests[0].frame()).toBeTruthy();
    });
    it('Page.Events.RequestFinished', async () => {
      const { page, server } = getTestState();

      const requests = [];
      page.on('requestfinished', (request) => requests.push(request));
      await page.goto(server.EMPTY_PAGE);
      expect(requests.length).toBe(1);
      expect(requests[0].url()).toBe(server.EMPTY_PAGE);
      expect(requests[0].response()).toBeTruthy();
      expect(requests[0].frame() === page.mainFrame()).toBe(true);
      expect(requests[0].frame().url()).toBe(server.EMPTY_PAGE);
    });
    it('should fire events in proper order', async () => {
      const { page, server } = getTestState();

      const events = [];
      page.on('request', (request) => events.push('request'));
      page.on('response', (response) => events.push('response'));
      page.on('requestfinished', (request) => events.push('requestfinished'));
      await page.goto(server.EMPTY_PAGE);
      expect(events).toEqual(['request', 'response', 'requestfinished']);
    });
    it('should support redirects', async () => {
      const { page, server } = getTestState();

      const events = [];
      page.on('request', (request) =>
        events.push(`${request.method()} ${request.url()}`)
      );
      page.on('response', (response) =>
        events.push(`${response.status()} ${response.url()}`)
      );
      page.on('requestfinished', (request) =>
        events.push(`DONE ${request.url()}`)
      );
      page.on('requestfailed', (request) =>
        events.push(`FAIL ${request.url()}`)
      );
      server.setRedirect('/foo.html', '/empty.html');
      const FOO_URL = server.PREFIX + '/foo.html';
      const response = await page.goto(FOO_URL);
      expect(events).toEqual([
        `GET ${FOO_URL}`,
        `302 ${FOO_URL}`,
        `DONE ${FOO_URL}`,
        `GET ${server.EMPTY_PAGE}`,
        `200 ${server.EMPTY_PAGE}`,
        `DONE ${server.EMPTY_PAGE}`,
      ]);

      // Check redirect chain
      const redirectChain = response.request().redirectChain();
      expect(redirectChain.length).toBe(1);
      expect(redirectChain[0].url()).toContain('/foo.html');
      expect(redirectChain[0].response().remoteAddress().port).toBe(
        server.PORT
      );
    });
  });

  describe('Request.isNavigationRequest', () => {
    itFailsFirefox('should work', async () => {
      const { page, server } = getTestState();

      const requests = new Map();
      page.on('request', (request) =>
        requests.set(request.url().split('/').pop(), request)
      );
      server.setRedirect('/rrredirect', '/frames/one-frame.html');
      await page.goto(server.PREFIX + '/rrredirect');
      expect(requests.get('rrredirect').isNavigationRequest()).toBe(true);
      expect(requests.get('one-frame.html').isNavigationRequest()).toBe(true);
      expect(requests.get('frame.html').isNavigationRequest()).toBe(true);
      expect(requests.get('script.js').isNavigationRequest()).toBe(false);
      expect(requests.get('style.css').isNavigationRequest()).toBe(false);
    });
    itFailsFirefox('should work with request interception', async () => {
      const { page, server } = getTestState();

      const requests = new Map();
      page.on('request', (request) => {
        requests.set(request.url().split('/').pop(), request);
        request.continue();
      });
      await page.setRequestInterception(true);
      server.setRedirect('/rrredirect', '/frames/one-frame.html');
      await page.goto(server.PREFIX + '/rrredirect');
      expect(requests.get('rrredirect').isNavigationRequest()).toBe(true);
      expect(requests.get('one-frame.html').isNavigationRequest()).toBe(true);
      expect(requests.get('frame.html').isNavigationRequest()).toBe(true);
      expect(requests.get('script.js').isNavigationRequest()).toBe(false);
      expect(requests.get('style.css').isNavigationRequest()).toBe(false);
    });
    it('should work when navigating to image', async () => {
      const { page, server } = getTestState();

      const requests = [];
      page.on('request', (request) => requests.push(request));
      await page.goto(server.PREFIX + '/pptr.png');
      expect(requests[0].isNavigationRequest()).toBe(true);
    });
  });

  describeFailsFirefox('Page.setExtraHTTPHeaders', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      await page.setExtraHTTPHeaders({
        foo: 'bar',
      });
      const [request] = await Promise.all([
        server.waitForRequest('/empty.html'),
        page.goto(server.EMPTY_PAGE),
      ]);
      expect(request.headers['foo']).toBe('bar');
    });
    it('should throw for non-string header values', async () => {
      const { page } = getTestState();

      let error = null;
      try {
        await page.setExtraHTTPHeaders({ foo: 1 });
      } catch (error_) {
        error = error_;
      }
      expect(error.message).toBe(
        'Expected value of header "foo" to be String, but "number" is found.'
      );
    });
  });

  describeFailsFirefox('Page.authenticate', function () {
    it('should work', async () => {
      const { page, server } = getTestState();

      server.setAuth('/empty.html', 'user', 'pass');
      let response = await page.goto(server.EMPTY_PAGE);
      expect(response.status()).toBe(401);
      await page.authenticate({
        username: 'user',
        password: 'pass',
      });
      response = await page.reload();
      expect(response.status()).toBe(200);
    });
    it('should fail if wrong credentials', async () => {
      const { page, server } = getTestState();

      // Use unique user/password since Chrome caches credentials per origin.
      server.setAuth('/empty.html', 'user2', 'pass2');
      await page.authenticate({
        username: 'foo',
        password: 'bar',
      });
      const response = await page.goto(server.EMPTY_PAGE);
      expect(response.status()).toBe(401);
    });
    it('should allow disable authentication', async () => {
      const { page, server } = getTestState();

      // Use unique user/password since Chrome caches credentials per origin.
      server.setAuth('/empty.html', 'user3', 'pass3');
      await page.authenticate({
        username: 'user3',
        password: 'pass3',
      });
      let response = await page.goto(server.EMPTY_PAGE);
      expect(response.status()).toBe(200);
      await page.authenticate(null);
      // Navigate to a different origin to bust Chrome's credential caching.
      response = await page.goto(server.CROSS_PROCESS_PREFIX + '/empty.html');
      expect(response.status()).toBe(401);
    });
  });
});

"""
