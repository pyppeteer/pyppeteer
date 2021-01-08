#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import glob
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from unittest import mock

import pytest
import websockets
from pyppeteer.errors import NetworkError
from pyppeteer.launcher import launcher
from pyppeteer.util import get_free_port
from syncer import sync

from .utils.server import get_application


class TestLauncher(unittest.TestCase):
    # def setUp(self):
    #     self.headless_options = [
    #         '--headless',
    #         '--hide-scrollbars',
    #         '--mute-audio',
    #     ]
    #     if current_platform().startswith('win'):
    #         self.headless_options.append('--disable-gpu')

    def check_default_args(self, launcher):
        for opt in self.headless_options:
            assert opt in launcher.chromeArguments
        assert any(opt for opt in launcher.chromeArguments if opt.startswith('--user-data-dir'))

    def test_no_option(self):
        launcher = Launcher()
        self.check_default_args(launcher)
        assert launcher.chromeExecutable == str(chromium_executable())

    def test_disable_headless(self):
        launcher = Launcher({'headless': False})
        for opt in self.headless_options:
            assert opt not in launcher.chromeArguments

    def test_disable_default_args(self):
        launcher = Launcher(ignoreDefaultArgs=True)
        # check default args
        assert '--no-first-run' not in launcher.chromeArguments
        # check automation args
        assert '--enable-automation' not in launcher.chromeArguments

    def test_executable(self):
        launcher = Launcher({'executablePath': '/path/to/chrome'})
        assert launcher.chromeExecutable == '/path/to/chrome'

    def test_args(self):
        launcher = Launcher({'args': ['--some-args']})
        self.check_default_args(launcher)
        assert '--some-args' in launcher.chromeArguments

    def test_filter_ignore_default_args(self):
        _defaultArgs = defaultArgs()
        options = deepcopy(DEFAULT_OPTIONS)
        launcher = Launcher(
            options,
            # ignore first and third default arguments
            ignoreDefaultArgs=[_defaultArgs[0], _defaultArgs[2]],
        )
        assert _defaultArgs[0] not in launcher.cmd
        assert _defaultArgs[1] in launcher.cmd
        assert _defaultArgs[2] not in launcher.cmd

    def test_user_data_dir(self):
        launcher = Launcher({'args': ['--user-data-dir=/path/to/profile']})
        self.check_default_args(launcher)
        assert '--user-data-dir=/path/to/profile' in launcher.chromeArguments
        assert launcher.temporaryUserDataDir is None

    @sync
    async def test_close_no_connection(self):
        browser = await launch(args=['--no-sandbox'])
        await browser.close()

    @sync
    async def test_launch(self):
        browser = await launch(DEFAULT_OPTIONS)
        await browser.newPage()
        await browser.close()

    @unittest.skip('should fix ignoreHTTPSErrors.')
    @sync
    async def test_ignore_https_errors(self):
        browser = await launch(DEFAULT_OPTIONS, ignoreHTTPSErrors=True)
        page = await browser.newPage()
        port = get_free_port()
        time.sleep(0.1)
        app = get_application()
        server = app.listen(port)
        response = await page.goto('https://localhost:{}'.format(port))
        assert response.ok
        await browser.close()
        server.stop()

    @sync
    async def test_ignore_https_errors_interception(self):
        browser = await launch(DEFAULT_OPTIONS, ignoreHTTPSErrors=True)
        page = await browser.newPage()
        await page.setRequestInterception(True)

        async def check(req) -> None:
            await req.continue_()

        page.on('request', lambda req: asyncio.ensure_future(check(req)))
        # TODO: should use user-signed cert
        response = await page.goto('https://google.com/')
        assert response is not None
        assert response.status == 200

    @sync
    async def test_await_after_close(self):
        browser = await launch(DEFAULT_OPTIONS)
        page = await browser.newPage()
        promise = page.evaluate('() => new Promise(r => {})')
        await browser.close()
        with pytest.raises(NetworkError):
            await promise

    @sync
    async def test_invalid_executable_path(self):
        with pytest.raises(FileNotFoundError):
            await launch(DEFAULT_OPTIONS, executablePath='not-a-path')

    @unittest.skipIf(sys.platform.startswith('win'), 'skip on windows')
    def test_dumpio_default(self):
        basedir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(basedir, 'dumpio.py')
        proc = subprocess.run([sys.executable, path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
        assert 'DUMPIO_TEST' not in proc.stdout.decode()
        assert 'DUMPIO_TEST' not in proc.stderr.decode()

    @unittest.skipIf(sys.platform.startswith('win'), 'skip on windows')
    def test_dumpio_enable(self):
        basedir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(basedir, 'dumpio.py')
        proc = subprocess.run([sys.executable, path, '--dumpio'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
        # console.log output is sent to stderr
        assert 'DUMPIO_TEST' not in proc.stdout.decode()
        assert 'DUMPIO_TEST' in proc.stderr.decode()

    @sync
    async def test_default_viewport(self):
        options = deepcopy(DEFAULT_OPTIONS)
        options['defaultViewport'] = {
            'width': 456,
            'height': 789,
        }
        browser = await launch(options)
        page = await browser.newPage()
        assert await page.evaluate('window.innerWidth') == 456
        assert await page.evaluate('window.innerHeight') == 789
        await browser.close()

    @sync
    async def test_disable_default_viewport(self):
        options = deepcopy(DEFAULT_OPTIONS)
        options['defaultViewport'] = None
        browser = await launch(options)
        page = await browser.newPage()
        assert page.viewport is None
        await browser.close()


class TestDefaultURL(unittest.TestCase):
    @sync
    async def test_default_url(self):
        browser = await launch(DEFAULT_OPTIONS)
        pages = await browser.pages
        url_list = []
        for page in pages:
            url_list.append(page.url)
        assert url_list == ['about:blank']
        await browser.close()

    @unittest.skipIf('CI' in os.environ, 'Skip in-browser test on CI')
    @sync
    async def test_default_url_not_headless(self):
        options = deepcopy(DEFAULT_OPTIONS)
        options['headless'] = False
        browser = await launch(options)
        pages = await browser.pages
        url_list = []
        for page in pages:
            url_list.append(page.url)
        assert url_list == ['about:blank']
        await browser.close()

    @sync
    async def test_custom_url(self):
        customUrl = 'http://example.com/'
        options = deepcopy(DEFAULT_OPTIONS)
        options['args'].append(customUrl)
        browser = await launch(options)
        pages = await browser.pages
        assert len(pages) == 1
        if pages[0].url != customUrl:
            await pages[0].waitForNavigation()
        assert pages[0].url == customUrl
        await browser.close()


class TestMixedContent(unittest.TestCase):
    @unittest.skip('need server-side implementation')
    @sync
    async def test_mixed_content(self) -> None:
        options = {'ignoreHTTPSErrors': True}
        options.update(DEFAULT_OPTIONS)
        browser = await launch(options)
        page = await browser.newPage()
        # page.goto()
        await page.close()
        await browser.close()


class TestLogLevel(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger('pyppeteer')
        self.mock = mock.Mock()
        self._orig_stderr = sys.stderr.write
        sys.stderr.write = self.mock

    def tearDown(self):
        sys.stderr.write = self._orig_stderr
        logging.getLogger('pyppeteer').setLevel(logging.NOTSET)

    @sync
    async def test_level_default(self):
        browser = await launch(args=['--no-sandbox'])
        await browser.close()

        assert self.logger.isEnabledFor(logging.WARN)
        assert not self.logger.isEnabledFor(logging.INFO)
        assert not self.logger.isEnabledFor(logging.DEBUG)
        self.mock.assert_not_called()

    # @unittest.skipIf(current_platform().startswith('win'), 'error on windows')
    @sync
    async def test_level_info(self):
        browser = await launch(args=['--no-sandbox'], logLevel=logging.INFO)
        await browser.close()

        assert self.logger.isEnabledFor(logging.WARN)
        assert self.logger.isEnabledFor(logging.INFO)
        assert not self.logger.isEnabledFor(logging.DEBUG)

        assert 'listening on' in self.mock.call_args_list[0][0][0]

    # @unittest.skipIf(current_platform().startswith('win'), 'error on windows')
    @sync
    async def test_level_debug(self):
        browser = await launch(args=['--no-sandbox'], logLevel=logging.DEBUG)
        await browser.close()

        assert self.logger.isEnabledFor(logging.WARN)
        assert self.logger.isEnabledFor(logging.INFO)
        assert self.logger.isEnabledFor(logging.DEBUG)

        assert 'listening on' in self.mock.call_args_list[0][0][0]
        if self.mock.call_args_list[1][0][0] == '\n':
            # python < 3.7.3
            assert 'SEND' in self.mock.call_args_list[2][0][0]
            assert 'RECV' in self.mock.call_args_list[4][0][0]
        else:
            assert 'SEND' in self.mock.call_args_list[1][0][0]
            assert 'RECV' in self.mock.call_args_list[2][0][0]

    # @unittest.skipIf(current_platform().startswith('win'), 'error on windows')
    @sync
    async def test_connect_debug(self):
        browser = await launch(args=['--no-sandbox'])
        browser2 = await connect(browserWSEndpoint=browser.wsEndpoint, logLevel=logging.DEBUG,)
        page = await browser2.newPage()
        await page.close()
        await browser2.disconnect()
        await browser.close()

        assert self.logger.isEnabledFor(logging.WARN)
        assert self.logger.isEnabledFor(logging.INFO)
        assert self.logger.isEnabledFor(logging.DEBUG)

        assert 'SEND' in self.mock.call_args_list[0][0][0]
        assert 'RECV' in self.mock.call_args_list[2][0][0]


class TestUserDataDir(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        time.sleep(0.1)
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.url = 'http://localhost:{}/'.format(cls.port)

    def setUp(self):
        self.datadir = tempfile.mkdtemp()

    def tearDown(self):
        if 'CI' not in os.environ:
            for _ in range(100):
                shutil.rmtree(self.datadir, ignore_errors=True)
                if os.path.exists(self.datadir):
                    time.sleep(0.01)
                else:
                    break
            else:
                raise IOError('Unable to remove Temporary User Data')

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    @unittest.skipIf(sys.platform.startswith('cyg'), 'Fails on cygwin')
    @sync
    async def test_user_data_dir_option(self):
        browser = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        # Open a page to make sure its functional
        await browser.newPage()
        assert len(glob.glob(os.path.join(self.datadir, '**'))) > 0
        await browser.close()
        assert len(glob.glob(os.path.join(self.datadir, '**'))) > 0

    @unittest.skipIf(sys.platform.startswith('cyg'), 'Fails on cygwin')
    @sync
    async def test_user_data_dir_args(self):
        options = {}
        options.update(DEFAULT_OPTIONS)
        options['args'] = options['args'] + ['--user-data-dir={}'.format(self.datadir)]
        browser = await launch(options)
        assert len(glob.glob(os.path.join(self.datadir, '**'))) > 0
        await browser.close()
        assert len(glob.glob(os.path.join(self.datadir, '**'))) > 0

    @sync
    async def test_user_data_dir_restore_state(self):
        browser = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        page = await browser.newPage()
        await page.goto(self.url + 'empty')
        await page.evaluate('() => localStorage.hey = "hello"')
        await browser.close()

        browser2 = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        page2 = await browser2.newPage()
        await page2.goto(self.url + 'empty')
        result = await page2.evaluate('() => localStorage.hey')
        await browser2.close()
        assert result == 'hello'

    @unittest.skipIf('CI' in os.environ, 'skip in-browser test on CI server')
    @sync
    async def test_user_data_dir_restore_cookie_in_browser(self):
        browser = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir, headless=False)
        page = await browser.newPage()
        await page.goto(self.url + 'empty')
        await page.evaluate('() => document.cookie = "foo=true; expires=Fri, 31 Dec 9999 23:59:59 GMT"')
        await browser.close()

        browser2 = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        page2 = await browser2.newPage()
        await page2.goto(self.url + 'empty')
        result = await page2.evaluate('() => document.cookie')
        await browser2.close()
        assert result == 'foo=true'


class TestTargetEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        time.sleep(0.1)
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.url = 'http://localhost:{}/'.format(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    @sync
    async def test_target_events(self):
        browser = await launch(DEFAULT_OPTIONS)
        events = []
        browser.on('targetcreated', lambda _: events.append('CREATED'))
        browser.on('targetchanged', lambda _: events.append('CHANGED'))
        browser.on('targetdestroyed', lambda _: events.append('DESTROYED'))
        page = await browser.newPage()
        await page.goto(self.url + 'empty')
        await page.close()
        assert ['CREATED', 'CHANGED', 'DESTROYED'] == events
        await browser.close()


class TestClose(unittest.TestCase):
    @sync
    async def test_close(self):
        curdir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(curdir, 'closeme.py')
        proc = subprocess.run([sys.executable, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,)
        assert proc.returncode == 0
        wsEndPoint = proc.stdout.decode()
        # chrome should be already closed, so fail to connect websocket
        with pytest.raises(OSError):
            await websockets.client.connect(wsEndPoint)


class TestEventLoop(unittest.TestCase):
    def test_event_loop(self):
        loop = asyncio.new_event_loop()

        async def inner(_loop) -> None:
            browser = await launch(args=['--no-sandbox'], loop=_loop)
            page = await browser.newPage()
            await page.goto('http://example.com')
            result = await page.evaluate('() => 1 + 2')
            assert result == 3
            await page.close()
            await browser.close()

        loop.run_until_complete(inner(loop))


class TestConnect(unittest.TestCase):
    @sync
    async def test_connect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browser2 = await connect(browserWSEndpoint=browser.wsEndpoint)
        page = await browser2.newPage()
        assert await page.evaluate('() => 7 * 8') == 56

        await browser2.disconnect()
        page2 = await browser.newPage()
        assert await page2.evaluate('() => 7 * 6') == 42
        await browser.close()

    @sync
    async def test_reconnect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browserWSEndpoint = browser.wsEndpoint
        await browser.disconnect()

        browser2 = await connect(browserWSEndpoint=browserWSEndpoint)
        page = await browser2.newPage()
        assert await page.evaluate('() => 7 * 8') == 56
        await browser.close()

    @unittest.skip('This test hangs')
    @sync
    async def test_fail_to_connect_closed_chrome(self):
        browser = await launch(DEFAULT_OPTIONS)
        browserWSEndpoint = browser.wsEndpoint
        await browser.close()
        with pytest.raises(Exception):
            await connect(browserWSEndpoint=browserWSEndpoint)

    @sync
    async def test_executable_path(self):
        assert os.path.exists(executablePath())
