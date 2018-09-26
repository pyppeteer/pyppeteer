#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from syncer import sync

import pyppeteer
from pyppeteer.errors import ElementHandleError

from .base import BaseTestCase
from .frame_utils import attachFrame


class TestBoundingBox(BaseTestCase):
    @sync
    async def test_bounding_box(self):
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.goto(self.url + 'static/grid.html')
        elementHandle = await self.page.J('.box:nth-of-type(13)')
        box = await elementHandle.boundingBox()
        self.assertEqual({'x': 100, 'y': 50, 'width': 50, 'height': 50}, box)

    @sync
    async def test_nested_frame(self):
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.goto(self.url + 'static/nested-frames.html')
        nestedFrame = self.page.frames[1].childFrames[1]
        elementHandle = await nestedFrame.J('div')
        box = await elementHandle.boundingBox()
        # Frame size is unstable
        # Frame order is unstable
        # self.assertIn(box, [
        #     {'x': 28, 'y': 28, 'width': 264, 'height': 16},
        #     {'x': 28, 'y': 260, 'width': 264, 'height': 16},
        # ])
        self.assertEqual(box['x'], 28)
        self.assertIn(box['y'], [28, 260])
        self.assertEqual(box['width'], 264)

    @sync
    async def test_invisible_element(self):
        await self.page.setContent('<div style="display: none;">hi</div>')
        element = await self.page.J('div')
        self.assertIsNone(await element.boundingBox())

    @sync
    async def test_force_layout(self):
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.setContent(
            '<div style="width: 100px; height: 100px;">hello</div>')
        elementHandle = await self.page.J('div')
        await self.page.evaluate(
            'element => element.style.height = "200px"',
            elementHandle,
        )
        box = await elementHandle.boundingBox()
        self.assertEqual(box, {
            'x': 8,
            'y': 8,
            'width': 100,
            'height': 200,
        })

    @sync
    async def test_svg(self):
        await self.page.setContent('''
            <svg xmlns="http://www.w3.org/2000/svg" width="500" height="500">
                <rect id="theRect" x="30" y="50" width="200" height="300"></rect>
            </svg>
        ''')  # noqa: E501
        element = await self.page.J('#therect')
        pptrBoundingBox = await element.boundingBox()
        webBoundingBox = await self.page.evaluate('''e => {
            const rect = e.getBoundingClientRect();
            return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
        }''', element)  # noqa: E501
        self.assertEqual(pptrBoundingBox, webBoundingBox)


class TestBoxModel(BaseTestCase):
    def setUp(self):
        self._old_debug = pyppeteer.DEBUG
        super().setUp()

    def tearDown(self):
        super().tearDown()
        pyppeteer.DEBUG = self._old_debug

    @sync
    async def test_box_model(self):
        await self.page.goto(self.url + 'static/resetcss.html')

        # add frame and position it absolutely
        await attachFrame(
            self.page, 'frame1', self.url + 'static/resetcss.html')
        await self.page.evaluate('''() => {
            const frame = document.querySelector('#frame1');
            frame.style = `
                position: absolute;
                left: 1px;
                top: 2px;
            `;
        }''')

        # add div and position it absolutely inside frame
        frame = self.page.frames[1]
        divHandle = (await frame.evaluateHandle('''() => {
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
        }''')).asElement()

        # query div's boxModel and assert box values
        box = await divHandle.boxModel()
        self.assertEqual(box['width'], 6)
        self.assertEqual(box['height'], 7)
        self.assertEqual(box['margin'][0], {
            'x': 1 + 4,
            'y': 2 + 5,
        })
        self.assertEqual(box['border'][0], {
            'x': 1 + 4 + 3,
            'y': 2 + 5,
        })
        self.assertEqual(box['padding'][0], {
            'x': 1 + 4 + 3 + 1,
            'y': 2 + 5,
        })
        self.assertEqual(box['content'][0], {
            'x': 1 + 4 + 3 + 1 + 2,
            'y': 2 + 5,
        })

    @sync
    async def test_box_model_invisible(self):
        await self.page.setContent('<div style="display:none;">hi</div>')
        element = await self.page.J('div')
        with self.assertLogs('pyppeteer.element_handle', logging.DEBUG):
            self.assertIsNone(await element.boxModel())

    @sync
    async def test_debug_error(self):
        await self.page.setContent('<div style="display:none;">hi</div>')
        element = await self.page.J('div')
        pyppeteer.DEBUG = True
        with self.assertLogs('pyppeteer.element_handle', logging.ERROR):
            self.assertIsNone(await element.boxModel())
        pyppeteer.DEBUG = False
        with self.assertRaises(AssertionError):
            with self.assertLogs('pyppeteer.element_handle', logging.INFO):
                self.assertIsNone(await element.boxModel())


class TestContentFrame(BaseTestCase):
    @sync
    async def test_content_frame(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        elementHandle = await self.page.J('#frame1')
        frame = await elementHandle.contentFrame()
        self.assertEqual(frame, self.page.frames[1])


class TestClick(BaseTestCase):
    @sync
    async def test_clik(self):
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await button.click()
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')

    @sync
    async def test_shadow_dom(self):
        await self.page.goto(self.url + 'static/shadow.html')
        button = await self.page.evaluateHandle('() => button')
        await button.click()
        self.assertTrue(await self.page.evaluate('clicked'))

    @sync
    async def test_text_node(self):
        await self.page.goto(self.url + 'static/button.html')
        buttonTextNode = await self.page.evaluateHandle(
            '() => document.querySelector("button").firstChild')
        with self.assertRaises(ElementHandleError) as cm:
            await buttonTextNode.click()
        self.assertEqual('Node is not of type HTMLElement',
                         cm.exception.args[0])

    @sync
    async def test_detached_node(self):
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate('btn => btn.remove()', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual('Node is detached from document',
                         cm.exception.args[0])

    @sync
    async def test_hidden_node(self):
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate('btn => btn.style.display = "none"', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual(
            'Node is either not visible or not an HTMLElement',
            cm.exception.args[0],
        )

    @sync
    async def test_recursively_hidden_node(self):
        await self.page.goto(self.url + 'static/button.html')
        button = await self.page.J('button')
        await self.page.evaluate(
            'btn => btn.parentElement.style.display = "none"', button)
        with self.assertRaises(ElementHandleError) as cm:
            await button.click()
        self.assertEqual(
            'Node is either not visible or not an HTMLElement',
            cm.exception.args[0],
        )

    @sync
    async def test_br_node(self):
        await self.page.setContent('hello<br>goodbye')
        br = await self.page.J('br')
        with self.assertRaises(ElementHandleError) as cm:
            await br.click()
        self.assertEqual(
            'Node is either not visible or not an HTMLElement',
            cm.exception.args[0],
        )


class TestHover(BaseTestCase):
    @sync
    async def test_hover(self):
        await self.page.goto(self.url + 'static/scrollable.html')
        button = await self.page.J('#button-6')
        await button.hover()
        self.assertEqual(
            await self.page.evaluate(
                'document.querySelector("button:hover").id'),
            'button-6'
        )


class TestIsIntersectingViewport(BaseTestCase):
    @sync
    async def test_is_intersecting_viewport(self):
        await self.page.goto(self.url + 'static/offscreenbuttons.html')
        for i in range(11):
            button = await self.page.J('#btn{}'.format(i))
            visible = i < 10
            self.assertEqual(await button.isIntersectingViewport(), visible)


class TestScreenshot(BaseTestCase):
    @sync
    async def test_screenshot_larger_than_viewport(self):
        await self.page.setViewport({'width': 500, 'height': 500})
        await self.page.setContent('''
something above
<style>
div.to-screenshot {
    border: 1px solid blue;
    width: 600px;
    height: 600px;
    margin-left: 50px;
}

::-webkit-scrollbar {
    display: none;
}
</style>

<div class="to-screenshot"></div>
                                   ''')
        elementHandle = await self.page.J('div.to-screenshot')
        await elementHandle.screenshot()
        size = await self.page.evaluate(
            '() => ({ w: window.innerWidth, h: window.innerHeight })'
        )
        self.assertEqual({'w': 500, 'h': 500}, size)


class TestQuerySelector(BaseTestCase):
    @sync
    async def test_J(self):
        await self.page.setContent('''
<html><body><div class="second"><div class="inner">A</div></div></body></html>
        ''')
        html = await self.page.J('html')
        second = await html.J('.second')
        inner = await second.J('.inner')
        content = await self.page.evaluate('e => e.textContent', inner)
        self.assertEqual(content, 'A')

    @sync
    async def test_J_none(self):
        await self.page.setContent('''
<html><body><div class="second"><div class="inner">A</div></div></body></html>
        ''')
        html = await self.page.J('html')
        second = await html.J('.third')
        self.assertIsNone(second)

    @sync
    async def test_Jeval(self):
        await self.page.setContent('''<html><body>
            <div class="tweet">
                <div class="like">100</div>
                <div class="retweets">10</div>
            </div>
        </body></html>''')
        tweet = await self.page.J('.tweet')
        content = await tweet.Jeval('.like', 'node => node.innerText')
        self.assertEqual(content, '100')

    @sync
    async def test_Jeval_subtree(self):
        htmlContent = '<div class="a">not-a-child-div</div><div id="myId"><div class="a">a-child-div</div></div>'  # noqa: E501
        await self.page.setContent(htmlContent)
        elementHandle = await self.page.J('#myId')
        content = await elementHandle.Jeval('.a', 'node => node.innerText')
        self.assertEqual(content, 'a-child-div')

    @sync
    async def test_Jeval_with_missing_selector(self):
        htmlContent = '<div class="a">not-a-child-div</div><div id="myId"></div>'  # noqa: E501
        await self.page.setContent(htmlContent)
        elementHandle = await self.page.J('#myId')
        with self.assertRaises(ElementHandleError) as cm:
            await elementHandle.Jeval('.a', 'node => node.innerText')
        self.assertIn('Error: failed to find element matching selector ".a"',
                      cm.exception.args[0])

    @sync
    async def test_JJ(self):
        await self.page.setContent('''
<html><body><div>A</div><br/><div>B</div></body></html>
        ''')
        html = await self.page.J('html')
        elements = await html.JJ('div')
        self.assertEqual(len(elements), 2)
        if sys.version_info >= (3, 6):
            result = []
            for elm in elements:
                result.append(
                    await self.page.evaluate('(e) => e.textContent', elm)
                )
            self.assertEqual(result, ['A', 'B'])

    @sync
    async def test_JJ_empty(self):
        await self.page.setContent('''
<html><body><span>A</span><br/><span>B</span></body></html>
        ''')
        html = await self.page.J('html')
        elements = await html.JJ('div')
        self.assertEqual(len(elements), 0)

    @sync
    async def test_JJEval(self):
        await self.page.setContent(
            '<html><body><div class="tweet"><div class="like">100</div>'
            '<div class="like">10</div></div></body></html>'
        )
        tweet = await self.page.J('.tweet')
        content = await tweet.JJeval(
            '.like', 'nodes => nodes.map(n => n.innerText)')
        self.assertEqual(content, ['100', '10'])

    @sync
    async def test_JJEval_subtree(self):
        await self.page.setContent(
            '<div class="a">not-a-child-div</div>'
            '<div id="myId">'
            '<div class="a">a1-child-div</div>'
            '<div class="a">a2-child-div</div>'
            '</div>'
        )
        elementHandle = await self.page.J('#myId')
        content = await elementHandle.JJeval(
            '.a', 'nodes => nodes.map(n => n.innerText)')
        self.assertEqual(content, ['a1-child-div', 'a2-child-div'])

    @sync
    async def test_JJEval_missing_selector(self):
        await self.page.setContent(
            '<div class="a">not-a-child-div</div><div id="myId"></div>')
        elementHandle = await self.page.J('#myId')
        nodesLength = await elementHandle.JJeval('.a', 'nodes => nodes.length')
        self.assertEqual(nodesLength, 0)

    @sync
    async def test_xpath(self):
        await self.page.setContent(
            '<html><body><div class="second"><div class="inner">A</div></div></body></html>'  # noqa: E501
        )
        html = await self.page.querySelector('html')
        second = await html.xpath('./body/div[contains(@class, \'second\')]')
        inner = await second[0].xpath('./div[contains(@class, \'inner\')]')
        content = await self.page.evaluate('(e) => e.textContent', inner[0])
        self.assertEqual(content, 'A')

    @sync
    async def test_xpath_not_found(self):
        await self.page.goto(self.url + 'empty')
        html = await self.page.querySelector('html')
        element = await html.xpath('/div[contains(@class, \'third\')]')
        self.assertEqual(element, [])
