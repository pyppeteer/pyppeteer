#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import pytest
from pyppeteer.errors import BrowserError
from syncer import sync

from .utils import attachFrame


class TestBoundingBox:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.setViewport({'width': 500, 'height': 500})
        await isolated_page.goto(server / 'grid.html')
        elementHandle = await isolated_page.J('.box:nth-of-type(13)')
        box = await elementHandle.boundingBox()
        assert {'x': 100, 'y': 50, 'width': 50, 'height': 50} == box

    @sync
    async def test_nested_frame(self, isolated_page, server, firefox):
        await isolated_page.setViewport({'width': 500, 'height': 500})
        await isolated_page.goto(server / 'frames/nested-frames.html')
        nestedFrame = isolated_page.frames[1].childFrames[1]
        await asyncio.sleep(5)
        elementHandle = await nestedFrame.J('div')
        box = await elementHandle.boundingBox()
        if firefox:
            assert box == {'x': 28, 'y': 182, 'width': 254, 'height': 18}
        else:
            assert box == {'x': 28, 'y': 260, 'width': 264, 'height': 18}

    @sync
    async def test_returns_None_for_invisible_element(self, isolated_page, server):
        await isolated_page.setContent('<div style="display: none;">hi</div>')
        element = await isolated_page.J('div')
        assert await element.boundingBox() is None

    @sync
    async def test_force_layout(self, isolated_page, server):
        await isolated_page.setViewport({'width': 500, 'height': 500})
        await isolated_page.setContent('<div style="width: 100px; height: 100px;">hello</div>')
        elementHandle = await isolated_page.J('div')
        await isolated_page.evaluate(
            'element => element.style.height = "200px"', elementHandle,
        )
        box = await elementHandle.boundingBox()
        assert box == {
            'x': 8,
            'y': 8,
            'width': 100,
            'height': 200,
        }

    @sync
    async def test_works_with_svg_nodes(self, isolated_page, server):
        await isolated_page.setContent(
            '''
            <svg xmlns="http://www.w3.org/2000/svg" width="500" height="500">
                <rect id="theRect" x="30" y="50" width="200" height="300"></rect>
            </svg>
        '''
        )
        element = await isolated_page.J('#therect')
        pptrBoundingBox = await element.boundingBox()
        webBoundingBox = await isolated_page.evaluate(
            '''e => {
            const rect = e.getBoundingClientRect();
            return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
        }''',
            element,
        )
        assert pptrBoundingBox == webBoundingBox


class TestBoxModel:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server / 'resetcss.html')

        # Step 1: Add Frame and position it absolutely.
        await attachFrame(isolated_page, server / 'resetcss.html', 'frame1')
        await isolated_page.evaluate(
            '''() => {
            const frame = document.querySelector('#frame1');
            frame.style = `
                position: absolute;
                left: 1px;
                top: 2px;
            `;
        }'''
        )

        # Step 2: Add div and position it absolutely inside frame.
        frame = isolated_page.frames[1]
        divHandle = (
            await frame.evaluateHandle(
                '''() => {
            const div = document.createElement('div');
            document.body.appendChild(div);
            div.style = `
                box-sizing: border-box;
                position: absolute;
                border-left: 1px solid black;
                padding-left: 2px;
                margin-left: 3px;
                left: 4px;
                top: 5px;
                width: 6px;
                height: 7px;
            `
            return div
        }'''
            )
        ).asElement()

        # Step 3: query div's boxModel and assert box values.
        box = await divHandle.boxModel()
        assert box['width'] == 6
        assert box['height'] == 7
        assert box['margin'][0] == {
            'x': 1 + 4,
            'y': 2 + 5,
        }
        assert box['border'][0] == {
            'x': 1 + 4 + 3,
            'y': 2 + 5,
        }
        assert box['padding'][0] == {
            'x': 1 + 4 + 3 + 1,
            'y': 2 + 5,
        }
        assert box['content'][0] == {
            'x': 1 + 4 + 3 + 1 + 2,
            'y': 2 + 5,
        }

    @sync
    async def test_returns_None_for_invisible_elements(self, isolated_page, server):
        await isolated_page.setContent('<div style="display:none;">hi</div>')
        element = await isolated_page.J('div')
        assert await element.boxModel() is None


class TestContentFrame:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await attachFrame(isolated_page, server.empty_page, 'frame1')
        elementHandle = await isolated_page.J('#frame1')
        frame = await elementHandle.contentFrame()
        assert frame == isolated_page.frames[1]


class TestClick:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server / 'input/button.html')
        button = await isolated_page.J('button')
        await button.click()
        assert await isolated_page.evaluate('result') == 'Clicked'

    @sync
    async def test_works_with_shadow_dom(self, isolated_page, server):
        await isolated_page.goto(server / 'shadow.html')
        button = await isolated_page.evaluateHandle('() => button')
        await button.click()
        assert await isolated_page.evaluate('clicked')

    @sync
    async def test_works_with_text_nodes(self, isolated_page, server):
        await isolated_page.goto(server / 'button.html')
        buttonTextNode = await isolated_page.evaluateHandle('() => document.querySelector("button").firstChild')
        with pytest.raises(BrowserError, match='Node is not of type HTMLElement'):
            await buttonTextNode.click()

    @sync
    async def test_raises_for_detached_nodes(self, isolated_page, server):
        await isolated_page.goto(server / 'button.html')
        button = await isolated_page.J('button')
        await isolated_page.evaluate('btn => btn.remove()', button)
        with pytest.raises(BrowserError, match='Node is detached from document') as cm:
            await button.click()

    @sync
    async def test_raises_for_hidden_nodes(self, isolated_page, server):
        await isolated_page.goto(server / 'button.html')
        button = await isolated_page.J('button')
        await isolated_page.evaluate('btn => btn.style.display = "none"', button)
        with pytest.raises(BrowserError, match='Node is either not visible or not an HTMLElement'):
            await button.click()

    @sync
    async def test_raises_for_recursively_hidden_node(self, isolated_page, server):
        await isolated_page.goto(server / 'button.html')
        button = await isolated_page.J('button')
        await isolated_page.evaluate('btn => btn.parentElement.style.display = "none"', button)
        with pytest.raises(BrowserError, match='Node is either not visible or not an HTMLElement'):
            await button.click()

    @sync
    async def test_raises_for_br_elements(self, isolated_page, server):
        await isolated_page.setContent('hello<br>goodbye')
        br = await isolated_page.J('br')
        with pytest.raises(BrowserError, match='Node is either not visible or not an HTMLElement'):
            await br.click()


class TestHover:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server / 'input/scrollable.html')
        button = await isolated_page.J('#button-6')
        await button.hover()
        assert await isolated_page.evaluate('document.querySelector("button:hover").id') == 'button-6'


class TestIsIntersectingViewport:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server / 'offscreenbuttons.html')
        for i in range(11):
            button = await isolated_page.J(f'#btn{i}')
            # All but last button are visible.
            visible = i < 10
            assert await button.isIntersectingViewport() == visible
