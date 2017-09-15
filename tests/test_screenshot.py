#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from unittest import TestCase

from syncer import sync

from pyppeteer.launcher import launch
from pyppeteer.errors import PageError

root_path = Path(__file__).resolve().parent
blank_png_path = root_path / 'blank_800x600.png'
blank_pdf_path = root_path / 'blank.pdf'


class TestScreenShot(TestCase):
    def setUp(self):
        self.browser = launch()
        self.target_path = Path(__file__).resolve().parent / 'test.png'
        if self.target_path.exists():
            self.target_path.unlink()

    @sync
    async def test_screenshot(self):
        page = await self.browser.newPage()
        await page.goto('about:blank')
        options = {'path': str(self.target_path)}
        self.assertFalse(self.target_path.exists())
        await page.screenshot(options)
        self.assertTrue(self.target_path.exists())

        with self.target_path.open('rb') as f:
            result = f.read()
        with blank_png_path.open('rb') as f:
            sample = f.read()
        self.assertEqual(result, sample)

    @sync
    async def test_unresolved_mimetype(self):
        page = await self.browser.newPage()
        await page.goto('about:blank')
        options = {'path': 'example.unsupported'}
        with self.assertRaises(PageError, msg='mime type: unsupported'):
            await page.screenshot(options)

    def tearDown(self):
        if self.target_path.exists():
            self.target_path.unlink()
        sync(self.browser.close())


class TestPDF(TestCase):
    def setUp(self):
        self.browser = launch()
        self.target_path = Path(__file__).resolve().parent / 'test.pdf'
        if self.target_path.exists():
            self.target_path.unlink()

    @sync
    async def test_pdf(self):
        page = await self.browser.newPage()
        await page.goto('about:blank')
        self.assertFalse(self.target_path.exists())
        await page.pdf(path=str(self.target_path))
        self.assertTrue(self.target_path.exists())
        self.assertTrue(self.target_path.stat().st_size >= 800)

    def tearDown(self):
        if self.target_path.exists:
            self.target_path.unlink()
        sync(self.browser.close())
