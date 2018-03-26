#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from base import BaseTestCase


class TestBoundingBox(BaseTestCase):
    @sync
    async def test_bounding_box(self) -> None:
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.goto(self.url + 'static/grid.html')
        elementHandle = await self.page.J('.box:nth-of-type(13)')
        box = await elementHandle.boundingBox()
        self.assertEqual({'x': 100, 'y': 50, 'width': 50, 'height': 50}, box)

    @sync
    async def test_nested_frame(self) -> None:
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.goto(self.url + 'static/nested-frames.html')
        nestedFrame = self.page.frames[1].childFrames[1]
        elementHandle = await nestedFrame.J('div')
        box = await elementHandle.boundingBox()
        # Frame order is unstable
        self.assertIn(box, [
            {'x': 28, 'y': 28, 'width': 264, 'height': 16},
            {'x': 28, 'y': 260, 'width': 264, 'height': 16},
        ])

    @sync
    async def test_invisible_element(self) -> None:
        await self.page.setContent('<div style="display: none;">hi</div>')
        element = await self.page.J('div')
        self.assertIsNone(await element.boundingBox())
