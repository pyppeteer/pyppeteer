#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from syncer import sync
import websockets

from pyppeteer import connect, launch, executablePath
from pyppeteer.chromium_downloader import chromium_excutable
from pyppeteer.errors import NetworkError
from pyppeteer.launcher import Launcher
from pyppeteer.util import get_free_port

from .base import DEFAULT_OPTIONS
from .server import get_application


class TestLauncher(unittest.TestCase):
    def setUp(self):
        self.headless_options = [
            '--headless',
            '--disable-gpu',
            '--hide-scrollbars',
            '--mute-audio',
        ]

    def check_default_args(self, launcher):
        for opt in self.headless_options:
            self.assertIn(opt, launcher.chrome_args)
        self.assertTrue(any(opt for opt in launcher.chrome_args
                            if opt.startswith('--user-data-dir')))

    def test_no_option(self):
        launcher = Launcher()
        self.check_default_args(launcher)
        self.assertEqual(launcher.exec, str(chromium_excutable()))

    def test_disable_headless(self):
        launcher = Launcher({'headless': False})
        for opt in self.headless_options:
            self.assertNotIn(opt, launcher.chrome_args)

    def test_disable_default_args(self):
        launcher = Launcher(ignoreDefaultArgs=True)
        # check defatul args
        self.assertNotIn('--no-first-run', launcher.chrome_args)
        # check dev tools port
        self.assertNotIn(
            '--remote-debugging-port={}'.format(launcher.port),
            launcher.chrome_args,
        )
        # check automation args
        self.assertNotIn('--enable-automation', launcher.chrome_args)

    def test_executable(self):
        launcher = Launcher({'executablePath': '/path/to/chrome'})
        self.assertEqual(launcher.exec, '/path/to/chrome')

    def test_args(self):
        launcher = Launcher({'args': ['--some-args']})
        self.check_default_args(launcher)
        self.assertIn('--some-args', launcher.chrome_args)

    def test_user_data_dir(self):
        launcher = Launcher({'args': ['--user-data-dir=/path/to/profile']})
        self.check_default_args(launcher)
        self.assertIn('--user-data-dir=/path/to/profile', launcher.chrome_args)
        self.assertIsNone(launcher._tmp_user_data_dir)

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
        self.assertTrue(response.ok)
        await browser.close()
        server.stop()

    @sync
    async def test_await_after_close(self):
        browser = await launch(DEFAULT_OPTIONS)
        page = await browser.newPage()
        promise = page.evaluate('() => new Promise(r => {})')
        await browser.close()
        with self.assertRaises(NetworkError):
            await promise

    @sync
    async def test_invalid_executable_path(self):
        with self.assertRaises(FileNotFoundError):
            await launch(DEFAULT_OPTIONS, executablePath='not-a-path')

    @unittest.skipIf(sys.platform.startswith('win'), 'skip on windows')
    def test_dumpio_default(self):
        basedir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(basedir, 'dumpio.py')
        proc = subprocess.run(
            [sys.executable, path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotIn('DUMPIO_TEST', proc.stdout.decode())
        self.assertNotIn('DUMPIO_TEST', proc.stderr.decode())

    @unittest.skipIf(sys.platform.startswith('win'), 'skip on windows')
    def test_dumpio_enable(self):
        basedir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(basedir, 'dumpio.py')
        proc = subprocess.run(
            [sys.executable, path, '--dumpio'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # console.log output is sent to stderr
        self.assertNotIn('DUMPIO_TEST', proc.stdout.decode())
        self.assertIn('DUMPIO_TEST', proc.stderr.decode())


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

    @sync
    async def test_user_data_dir_option(self):
        browser = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        self.assertGreater(len(glob.glob(os.path.join(self.datadir, '**'))), 0)
        await browser.close()
        self.assertGreater(len(glob.glob(os.path.join(self.datadir, '**'))), 0)

    @sync
    async def test_user_data_dir_args(self):
        options = {}
        options.update(DEFAULT_OPTIONS)
        options['args'] = (options['args'] +
                           ['--user-data-dir={}'.format(self.datadir)])
        browser = await launch(options)
        self.assertGreater(len(glob.glob(os.path.join(self.datadir, '**'))), 0)
        await browser.close()
        self.assertGreater(len(glob.glob(os.path.join(self.datadir, '**'))), 0)

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
        self.assertEqual(result, 'hello')

    @unittest.skipIf('CI' in os.environ, 'skip headful test on CI server')
    @sync
    async def test_user_data_dir_restore_cookie_headful(self):
        browser = await launch(
            DEFAULT_OPTIONS, userDataDir=self.datadir, headless=False)
        page = await browser.newPage()
        await page.goto(self.url + 'empty')
        await page.evaluate('() => document.cookie = "foo=true; expires=Fri, 31 Dec 9999 23:59:59 GMT"')  # noqa: E501
        await browser.close()

        browser2 = await launch(DEFAULT_OPTIONS, userDataDir=self.datadir)
        page2 = await browser2.newPage()
        await page2.goto(self.url + 'empty')
        result = await page2.evaluate('() => document.cookie')
        await browser2.close()
        self.assertEqual(result, 'foo=true')


class TestClose(unittest.TestCase):
    @sync
    async def test_close(self):
        curdir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(curdir, 'closeme.py')
        proc = subprocess.run(
            [sys.executable, path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(proc.returncode, 0)
        wsEndPoint = proc.stdout.decode()
        # chrome should be already closed, so fail to connet websocket
        with self.assertRaises(OSError):
            await websockets.client.connect(wsEndPoint)


class TestConnect(unittest.TestCase):
    @sync
    async def test_connect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browser2 = await connect(browserWSEndpoint=browser.wsEndpoint)
        page = await browser2.newPage()
        self.assertEqual(await page.evaluate('() => 7 * 8'), 56)

        await browser2.disconnect()
        page2 = await browser.newPage()
        self.assertEqual(await page2.evaluate('() => 7 * 6'), 42)
        await browser.close()

    @sync
    async def test_reconnect(self):
        browser = await launch(DEFAULT_OPTIONS)
        browserWSEndpoint = browser.wsEndpoint
        await browser.disconnect()

        browser2 = await connect(browserWSEndpoint=browserWSEndpoint)
        page = await browser2.newPage()
        self.assertEqual(await page.evaluate('() => 7 * 8'), 56)
        await browser.close()

    @unittest.skip('This test hangs')
    @sync
    async def test_fail_to_connect_closed_chrome(self):
        browser = await launch(DEFAULT_OPTIONS)
        browserWSEndpoint = browser.wsEndpoint
        await browser.close()
        with self.assertRaises(Exception):
            await connect(browserWSEndpoint=browserWSEndpoint)

    @sync
    async def test_executable_path(self):
        self.assertTrue(os.path.exists(executablePath()))
