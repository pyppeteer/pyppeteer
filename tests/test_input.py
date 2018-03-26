#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
