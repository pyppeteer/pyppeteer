#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import logging
from pathlib import Path

from syncer import sync

from .base import BaseTestCase


class TestPyppeteer(BaseTestCase):
    @sync
    async def test_get_https(self):
        await self.page.goto('https://example.com/')
        assert self.page.url == 'https://example.com/'

    @sync
    async def test_get_facebook(self):
        await self.page.goto('https://www.facebook.com/')
        assert self.page.url == 'https://www.facebook.com/'

    @sync
    async def test_plain_text_depr(self):
        await self.page.goto(self.url)
        with self.assertLogs('pyppeteer', logging.WARN) as log:
            text = await self.page.plainText()
            assert 'deprecated' in log.records[0].msg
        assert text.split() == ['Hello', 'link1', 'link2']

    @sync
    async def test_inject_file(self):  # deprecated
        tmp_file = Path('tmp.js')
        with tmp_file.open('w') as f:
            f.write(
                '''
() => document.body.appendChild(document.createElement("section"))
            '''.strip()
            )
        with self.assertLogs('pyppeteer', logging.WARN) as log:
            await self.page.injectFile(str(tmp_file))
            assert 'deprecated' in log.records[0].msg
        await self.page.waitForSelector('section')
        assert await self.page.J('section') is not None
        tmp_file.unlink()


class TestScreenshot(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.target_path = Path(__file__).resolve().parent / 'test.png'
        if self.target_path.exists():
            self.target_path.unlink()

    def tearDown(self):
        if self.target_path.exists():
            self.target_path.unlink()
        super().tearDown()

    @sync
    async def test_screenshot_large(self):
        page = await self.context.newPage()
        await page.setViewport(
            {'width': 2000, 'height': 2000,}
        )
        await page.goto(self.url + 'static/huge-page.html')
        options = {'path': str(self.target_path)}
        assert not self.target_path.exists()
        await asyncio.wait_for(page.screenshot(options), 30)
        assert self.target_path.exists()
        with self.target_path.open('rb') as fh:
            bytes = fh.read()
            assert len(bytes) > 2 ** 20
