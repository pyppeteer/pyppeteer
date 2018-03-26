#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import ElementHandleError

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


class TestClick(BaseTestCase):
    @sync
    async def test_clik(self) -> None:
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await button.click()
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')

    @sync
    async def test_chadow_dom(self) -> None:
        await self.page.goto(self.url + 'static/shadow.html')
        button = await self.page.evaluateHandle('() => button')
        await button.click()
        self.assertTrue(await self.page.evaluate('clicked'))

    @sync
    async def test_text_node(self) -> None:
        await self.page.goto(self.url + 'static/button.html')
        buttonTextNode = await self.page.evaluateHandle(
            '() => document.querySelector("button").firstChild')
        with self.assertRaises(ElementHandleError) as cm:
            await buttonTextNode.click()
        self.assertEqual('Node is not of type HTMLElement',
                         cm.exception.args[0])

    @sync
    async def test_detached_node(self) -> None:
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate('btn => btn.remove()', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual('Node is detached from document',
                         cm.exception.args[0])

    @sync
    async def test_hidden_node(self) -> None:
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate('btn => btn.style.display = "none"', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual('Node is not visible.', cm.exception.args[0])

    @sync
    async def test_recursively_hidden_node(self) -> None:
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate(
            'btn => btn.parentElement.style.display = "none"', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual('Node is not visible.', cm.exception.args[0])

    @sync
    async def test_br_node(self) -> None:
        await self.page.setContent('hello<br>goodbye')
        br = await self.page.J('br')
        with self.assertRaises(ElementHandleError) as cm:
            await br.click()
        self.assertEqual('Node is not visible.', cm.exception.args[0])


class TestHover(BaseTestCase):
    @sync
    async def test_hover(self) -> None:
        await self.page.goto(self.url + 'static/scrollable.html')
        button = await self.page.J('#button-6')
        await button.hover()
        self.assertEqual(
            await self.page.evaluate(
                'document.querySelector("button:hover").id'),
            'button-6'
        )
