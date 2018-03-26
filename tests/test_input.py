#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from syncer import sync

from pyppeteer.errors import PageError

from base import BaseTestCase


class TestClick(BaseTestCase):
    @sync
    async def test_click(self):
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')

    @sync
    async def test_click_events(self):
        await self.page.goto(self.url + 'static/checkbox.html')
        self.assertIsNone(await self.page.evaluate('result.check'))
        await self.page.click('input#agree')
        self.assertTrue(await self.page.evaluate('result.check'))
        events = await self.page.evaluate('result.events')
        self.assertEqual(events, [
            'mouseover',
            'mouseenter',
            'mousemove',
            'mousedown',
            'mouseup',
            'click',
            'input',
            'change',
        ])
        await self.page.click('input#agree')
        self.assertEqual(await self.page.evaluate('result.check'), False)

    @sync
    async def test_click_label(self):
        await self.page.goto(self.url + 'static/checkbox.html')
        self.assertIsNone(await self.page.evaluate('result.check'))
        await self.page.click('label[for="agree"]')
        self.assertTrue(await self.page.evaluate('result.check'))
        events = await self.page.evaluate('result.events')
        self.assertEqual(events, [
            'click',
            'input',
            'change',
        ])
        await self.page.click('label[for="agree"]')
        self.assertEqual(await self.page.evaluate('result.check'), False)

    @sync
    async def test_click_fail(self):
        await self.page.goto(self.url + 'static/button.html')
        with self.assertRaises(PageError) as cm:
            await self.page.click('button.does-not-exist')
        self.assertEqual(
            'No node found for selector: button.does-not-exist',
            cm.exception.args[0],
        )

    @sync
    async def test_touch_enabled_viewport(self):
        await self.page.setViewport({
            'width': 375,
            'height': 667,
            'deviceScaleFactor': 2,
            'isMobile': True,
            'hasTouch': True,
            'isLandscape': False,
        })
        await self.page.mouse.down()
        await self.page.mouse.move(100, 10)
        await self.page.mouse.up()

    @sync
    async def test_click_after_navigation(self):
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')


class TestFileUpload(BaseTestCase):
    @sync
    async def test_file_upload(self):
        await self.page.goto(self.url + 'static/fileupload.html')
        filePath = Path(__file__).parent / 'file-to-upload.txt'
        input = await self.page.J('input')
        await input.uploadFile(str(filePath))
        self.assertEqual(
            await self.page.evaluate('e => e.files[0].name', input),
            'file-to-upload.txt',
        )
        self.assertEqual(
            await self.page.evaluate('''e => {
                const reader = new FileReader();
                const promise = new Promise(fulfill => reader.onload = fulfill);
                reader.readAsText(e.files[0]);
                return promise.then(() => reader.result);
            }''', input),  # noqa: E501
            'contents of the file\n',
        )
