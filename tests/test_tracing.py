#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import unittest

from syncer import sync

from pyppeteer.errors import NetworkError

from .base import BaseTestCase


class TestTracing(BaseTestCase):
    def setUp(self):
        self.outfile = Path(__file__).parent / 'trace.json'
        if self.outfile.is_file():
            self.outfile.unlink()
        super().setUp()

    def tearDown(self):
        if self.outfile.is_file():
            self.outfile.unlink()
        super().tearDown()

    @sync
    async def test_tracing(self):
        await self.page.tracing.start({
            'path': str(self.outfile)
        })
        await self.page.goto(self.url)
        await self.page.tracing.stop()
        self.assertTrue(self.outfile.is_file())

    @sync
    async def test_custom_categories(self):
        await self.page.tracing.start({
            'path': str(self.outfile),
            'categories': ['disabled-by-default-v8.cpu_profiler.hires'],
        })
        await self.page.tracing.stop()
        self.assertTrue(self.outfile.is_file())
        with self.outfile.open() as f:
            trace_json = json.load(f)
        self.assertIn(
            'disabled-by-default-v8.cpu_profiler.hires',
            trace_json['metadata']['trace-config'],
        )

    @sync
    async def test_tracing_two_page_error(self):
        await self.page.tracing.start({'path': str(self.outfile)})
        new_page = await self.browser.newPage()
        with self.assertRaises(NetworkError):
            await new_page.tracing.start({'path': str(self.outfile)})
        await new_page.close()
        await self.page.tracing.stop()

    @sync
    async def test_return_buffer(self):
        await self.page.tracing.start(screenshots=True, path=str(self.outfile))
        await self.page.goto(self.url + 'static/grid.html')
        trace = await self.page.tracing.stop()
        with self.outfile.open('r') as f:
            buf = f.read()
        self.assertEqual(trace, buf)

    @unittest.skip('Not implemented')
    @sync
    async def test_return_null_on_error(self):
        await self.page.tracing.start(screenshots=True)
        await self.page.goto(self.url + 'static/grid.html')

    @sync
    async def test_without_path(self):
        await self.page.tracing.start(screenshots=True)
        await self.page.goto(self.url + 'static/grid.html')
        trace = await self.page.tracing.stop()
        self.assertIn('screenshot', trace)
