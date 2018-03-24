#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
import unittest

from syncer import sync

from pyppeteer.errors import ElementHandleError, TimeoutError

from base import BaseTestCase
from frame_utils import attachFrame, detachFrame


class TestContext(BaseTestCase):
    @sync
    async def test_frame_context(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        self.assertEqual(len(self.page.frames), 2)
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        context1 = await frame1.executionContext()
        context2 = await frame2.executionContext()
        self.assertTrue(context1)
        self.assertTrue(context2)

        await context1.evaluate('() => window.a = 1')
        await context2.evaluate('() => window.a = 2')
        a1 = await context1.evaluate('() => window.a')
        a2 = await context2.evaluate('() => window.a')
        self.assertEqual(a1, 1)
        self.assertEqual(a2, 2)


class TestEvaluate(BaseTestCase):
    @sync
    async def test_frame_evaluate(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        self.assertEqual(len(self.page.frames), 2)
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        await frame1.evaluate('() => window.a = 1')
        await frame2.evaluate('() => window.a = 2')
        a1 = await frame1.evaluate('window.a')
        a2 = await frame2.evaluate('window.a')
        self.assertEqual(a1, 1)
        self.assertEqual(a2, 2)

    @sync
    async def test_frame_evaluate_after_navigation(self):
        self.result = None

        def frame_navigated(frame):
            self.result = asyncio.ensure_future(frame.evaluate('6 * 7'))

        self.page.on('framenavigated', frame_navigated)
        await self.page.goto(self.url + 'empty')
        self.assertIsNotNone(self.result)
        self.assertEqual(await self.result, 42)

    @sync
    async def test_frame_cross_site(self):
        await self.page.goto(self.url + 'empty')
        mainFrame = self.page.mainFrame
        loc = await mainFrame.evaluate('window.location.href')
        self.assertIn('localhost', loc)
        await self.page.goto('http://127.0.0.1:{}/empty'.format(self.port))
        loc = await mainFrame.evaluate('window.location.href')
        self.assertIn('127.0.0.1', loc)


class TestWaitForFunction(BaseTestCase):
    def setUp(self):
        super().setUp()
        sync(self.page.goto(self.url + 'empty'))
        self.result = False

    def set_result(self, value):
        self.result = value

    @sync
    async def test_wait_for_expression(self):
        fut = asyncio.ensure_future(
            self.page.waitForFunction('window.__FOO === 1')
        )
        await self.page.evaluate('window.__FOO = 1;')
        await fut

    @sync
    async def test_wait_for_function(self):
        fut = asyncio.ensure_future(
            self.page.waitForFunction('() => window.__FOO === 1')
        )
        await self.page.evaluate('window.__FOO = 1;')
        await fut

    @sync
    async def test_wait_for_function_args(self):
        fut = asyncio.ensure_future(
            self.page.waitForFunction(
                '(a, b) => a + b === 3', {}, 1, 2)
        )
        await fut

    @sync
    async def test_poll_on_interval(self):
        result = []
        start_time = time.perf_counter()
        fut = asyncio.ensure_future(self.page.waitForFunction(
            '() => window.__FOO === "hit"', polling=100,
        ))
        fut.add_done_callback(lambda f: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await self.page.evaluate(
            'document.body.appendChild(document.createElement("div"))'
        )
        await asyncio.sleep(0.02)
        self.assertFalse(result)
        await fut
        self.assertGreater(time.perf_counter() - start_time, 0.1)
        self.assertEqual(await self.page.evaluate('window.__FOO'), 'hit')

    @sync
    async def test_poll_on_mutation(self):
        result = []
        fut = asyncio.ensure_future(self.page.waitForFunction(
            '() => window.__FOO === "hit"', polling='mutation',
        ))
        fut.add_done_callback(lambda f: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await asyncio.sleep(0.1)
        self.assertFalse(result)
        await self.page.evaluate(
            'document.body.appendChild(document.createElement("div"))'
        )
        await fut
        self.assertTrue(result)

    @sync
    async def test_poll_on_raf(self):
        result = []
        fut = asyncio.ensure_future(self.page.waitForFunction(
            '() => window.__FOO === "hit"', polling='raf',
        ))
        fut.add_done_callback(lambda f: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await asyncio.sleep(0)  # once switch task
        self.assertFalse(result)
        await fut
        self.assertTrue(result)

    @sync
    async def test_bad_polling_value(self):
        with self.assertRaises(ValueError) as cm:
            await self.page.waitForFunction('() => true', polling='unknown')
        self.assertIn('polling', cm.exception.args[0])

    @sync
    async def test_negative_polling_value(self):
        with self.assertRaises(ValueError) as cm:
            await self.page.waitForFunction('() => true', polling=-100)
        self.assertIn('Cannot poll with non-positive interval',
                      cm.exception.args[0])

    @sync
    async def test_wait_for_fucntion_return_value(self):
        result = await self.page.waitForFunction('() => 5')
        self.assertEqual(await result.jsonValue(), 5)

    @sync
    async def test_wait_for_function_window(self):
        self.assertTrue(await self.page.waitForFunction('() => window'))

    @sync
    async def test_wait_for_function_arg_element(self):
        await self.page.setContent('<div></div>')
        div = await self.page.J('div')
        fut = asyncio.ensure_future(
            self.page.waitForFunction('e => !e.parentElement', {}, div))
        fut.add_done_callback(lambda fut: self.set_result(True))
        await asyncio.sleep(0.1)
        self.assertFalse(self.result)
        await self.page.evaluate('e => e.remove()', div)
        await fut
        self.assertTrue(self.result)


class TestWaitForSelector(BaseTestCase):
    addElement = 'tag=>document.body.appendChild(document.createElement(tag))'

    def setUp(self):
        super().setUp()
        self.result = False
        sync(self.page.goto(self.url + 'empty'))

    def set_result(self, value: bool):
        self.result = value

    @sync
    async def test_wait_for_selector_immediate(self):
        frame = self.page.mainFrame
        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('*'))
        fut.add_done_callback(lambda fut: result.append(True))
        await fut
        self.assertTrue(result)

        result.clear()
        await frame.evaluate(self.addElement, 'div')
        fut = asyncio.ensure_future(frame.waitForSelector('div'))
        fut.add_done_callback(lambda fut: result.append(True))
        await fut
        self.assertTrue(result)

    @sync
    async def test_wait_for_selector_after_node_appear(self):
        frame = self.page.mainFrame

        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('div'))
        fut.add_done_callback(lambda fut: result.append(True))
        self.assertEqual(await frame.evaluate('() => 42'), 42)
        await asyncio.sleep(0.1)
        self.assertFalse(result)
        await frame.evaluate(self.addElement, 'br')
        await asyncio.sleep(0.1)
        self.assertFalse(result)
        await frame.evaluate(self.addElement, 'div')
        await fut
        self.assertTrue(result)

    @sync
    async def test_wait_for_selector_inner_html(self):
        fut = asyncio.ensure_future(self.page.waitForSelector('h3 div'))
        await self.page.evaluate(self.addElement, 'span')
        await self.page.evaluate('() => document.querySelector("span").innerHTML = "<h3><div></div></h3>"')  # noqa: E501
        await fut

    @sync
    async def test_shortcut_for_main_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        otherFrame = self.page.frames[1]
        fut = asyncio.ensure_future(self.page.waitForSelector('div'))
        fut.add_done_callback(lambda fut: self.set_result(True))
        await otherFrame.evaluate(self.addElement, 'div')
        await asyncio.sleep(0.1)
        self.assertFalse(self.result)
        await self.page.evaluate(self.addElement, 'div')
        await fut
        self.assertTrue(self.result)

    @sync
    async def test_run_in_specified_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        await attachFrame(self.page, 'frame2', self.url + 'empty')
        frame1 = self.page.frames[1]
        frame2 = self.page.frames[2]
        fut = asyncio.ensure_future(frame2.waitForSelector('div'))
        fut.add_done_callback(lambda fut: self.set_result(True))
        await frame1.evaluate(self.addElement, 'div')
        await asyncio.sleep(0.1)
        self.assertFalse(self.result)
        await frame2.evaluate(self.addElement, 'div')
        await fut
        self.assertTrue(self.result)

    @sync
    async def test_wait_for_selector_fail(self):
        await self.page.evaluate('() => document.querySelector = null')
        with self.assertRaises(ElementHandleError):
            await self.page.waitForSelector('*')

    @unittest.skip('Cannot catch error.')
    @sync
    async def test_fail_frame_detached(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        frame = self.page.frames[1]
        fut = frame.waitForSelector('.box')
        await detachFrame(self.page, 'frame1')
        with self.assertRaises(Exception):
            await fut

    @sync
    async def test_cross_process_navigation(self):
        fut = asyncio.ensure_future(self.page.waitForSelector('h1'))
        fut.add_done_callback(lambda fut: self.set_result(True))
        await self.page.goto(self.url + 'empty')
        await asyncio.sleep(0.1)
        self.assertFalse(self.result)
        await self.page.reload()
        await asyncio.sleep(0.1)
        self.assertFalse(self.result)
        await self.page.goto('http://127.0.0.1:{}/'.format(self.port))
        await fut
        self.assertTrue(self.result)

    @sync
    async def test_wait_for_selector_visible(self):
        div = []
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', visible=True))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent(
            '<div style="display: none; visibility: hidden;">1</div>'
        )
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await fut
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_visible_inner(self):
        div = []
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div#inner', visible=True))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent(
            '<div style="display: none; visibility: hidden;">'
            '<div id="inner">hi</div></div>'
        )
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await fut
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_hidden(self):
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.setProperty("visibility", "hidden")')  # noqa: E501
        await fut
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_display_none(self):
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").style.setProperty("display", "none")')  # noqa: E501
        await fut
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_remove(self):
        div = []
        await self.page.setContent('<div></div>')
        fut = asyncio.ensure_future(
            self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda fut: div.append(True))
        await asyncio.sleep(0.1)
        self.assertFalse(div)
        await self.page.evaluate('() => document.querySelector("div").remove()')  # noqa: E501
        await fut
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_timeout(self):
        with self.assertRaises(TimeoutError):
            await self.page.waitForSelector('div', timeout=10)

    @sync
    async def test_wait_for_selector_node_mutation(self):
        div = []
        fut = asyncio.ensure_future(self.page.waitForSelector('.cls'))
        fut.add_done_callback(lambda fut: div.append(True))
        await self.page.setContent('<div class="noCls"></div>')
        self.assertFalse(div)
        await self.page.evaluate(
            '() => document.querySelector("div").className="cls"'
        )
        await asyncio.sleep(0.1)
        self.assertTrue(div)

    @sync
    async def test_wait_for_selector_return_element(self):
        selector = asyncio.ensure_future(self.page.waitForSelector('.zombo'))
        await self.page.setContent('<div class="zombo">anything</div>')
        self.assertEqual(
            await self.page.evaluate('e => e.textContent', await selector),
            'anything',
        )
