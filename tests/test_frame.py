#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
import unittest

from syncer import sync

from pyppeteer.errors import ElementHandleError, NetworkError, TimeoutError

from .base import BaseTestCase
from .frame_utils import attachFrame, detachFrame, dumpFrames, navigateFrame
from .utils import waitEvent
import pytest

addElement = 'tag=>document.body.appendChild(document.createElement(tag))'


class TestContext(BaseTestCase):
    @sync
    async def test_frame_context(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        assert len(self.page.frames) == 2
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        context1 = await frame1.executionContext()
        context2 = await frame2.executionContext()
        assert context1
        assert context2
        assert context1 != context2
        assert context1.frame == frame1
        assert context2.frame == frame2

        await context1.evaluate('() => window.a = 1')
        await context2.evaluate('() => window.a = 2')
        a1 = await context1.evaluate('() => window.a')
        a2 = await context2.evaluate('() => window.a')
        assert a1 == 1
        assert a2 == 2


class TestEvaluateHandle(BaseTestCase):
    @sync
    async def test_evaluate_handle(self):
        await self.page.goto(self.url + 'empty')
        frame = self.page.mainFrame
        windowHandle = await frame.evaluateHandle('window')
        assert windowHandle


class TestEvaluate(BaseTestCase):
    @sync
    async def test_frame_evaluate(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        assert len(self.page.frames) == 2
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        await frame1.evaluate('() => window.a = 1')
        await frame2.evaluate('() => window.a = 2')
        a1 = await frame1.evaluate('window.a')
        a2 = await frame2.evaluate('window.a')
        assert a1 == 1
        assert a2 == 2

    @sync
    async def test_frame_evaluate_after_navigation(self):
        self.result = None

        def frame_navigated(frame):
            self.result = asyncio.ensure_future(frame.evaluate('6 * 7'))

        self.page.on('framenavigated', frame_navigated)
        await self.page.goto(self.url + 'empty')
        assert self.result is not None
        assert await self.result == 42

    @sync
    async def test_frame_cross_site(self):
        await self.page.goto(self.url + 'empty')
        mainFrame = self.page.mainFrame
        loc = await mainFrame.evaluate('window.location.href')
        assert 'localhost' in loc
        await self.page.goto('http://127.0.0.1:{}/empty'.format(self.port))
        loc = await mainFrame.evaluate('window.location.href')
        assert '127.0.0.1' in loc


class TestWaitForFunction(BaseTestCase):
    @sync
    async def test_wait_for_expression(self):
        fut = asyncio.ensure_future(self.page.waitForFunction('window.__FOO === 1'))
        await self.page.evaluate('window.__FOO = 1;')
        await fut

    @sync
    async def test_wait_for_function(self):
        fut = asyncio.ensure_future(self.page.waitForFunction('() => window.__FOO === 1'))
        await self.page.evaluate('window.__FOO = 1;')
        await fut

    @sync
    async def test_wait_for_function_args(self):
        fut = asyncio.ensure_future(self.page.waitForFunction('(a, b) => a + b === 3', {}, 1, 2))
        await fut

    @sync
    async def test_before_execution_context_resolved(self):
        await self.page.evaluateOnNewDocument('() => window.__RELOADED = true')
        await self.page.waitForFunction(
            '''() => {
            if (!window.__RELOADED)
                window.location.reload();
            return true;
        }'''
        )

    @sync
    async def test_poll_on_interval(self):
        result = []
        start_time = time.perf_counter()
        fut = asyncio.ensure_future(self.page.waitForFunction('() => window.__FOO === "hit"', polling=100,))
        fut.add_done_callback(lambda _: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await self.page.evaluate('document.body.appendChild(document.createElement("div"))')
        await asyncio.sleep(0.02)
        assert not result
        await fut
        assert time.perf_counter() - start_time > 0.1
        assert await self.page.evaluate('window.__FOO') == 'hit'

    @sync
    async def test_poll_on_mutation(self):
        result = []
        fut = asyncio.ensure_future(self.page.waitForFunction('() => window.__FOO === "hit"', polling='mutation',))
        fut.add_done_callback(lambda _: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await asyncio.sleep(0.1)
        assert not result
        await self.page.evaluate('document.body.appendChild(document.createElement("div"))')
        await fut
        assert result

    @sync
    async def test_poll_on_raf(self):
        result = []
        fut = asyncio.ensure_future(self.page.waitForFunction('() => window.__FOO === "hit"', polling='raf',))
        fut.add_done_callback(lambda _: result.append(True))
        await asyncio.sleep(0)  # once switch task
        await self.page.evaluate('window.__FOO = "hit"')
        await asyncio.sleep(0)  # once switch task
        assert not result
        await fut
        assert result

    @sync
    async def test_csp(self):
        await self.page.goto(self.url + 'csp')
        fut = asyncio.ensure_future(self.page.waitForFunction('() => window.__FOO === "hit"', polling='raf',))
        await self.page.evaluate('window.__FOO = "hit"')
        await fut

    @sync
    async def test_bad_polling_value(self):
        with pytest.raises(ValueError) as cm:
            await self.page.waitForFunction('() => true', polling='unknown')
        assert 'polling' in cm.exception.args[0]

    @sync
    async def test_negative_polling_value(self):
        with pytest.raises(ValueError) as cm:
            await self.page.waitForFunction('() => true', polling=-100)
        assert 'Cannot poll with non-positive interval' in cm.exception.args[0]

    @sync
    async def test_wait_for_function_return_value(self):
        result = await self.page.waitForFunction('() => 5')
        assert await result.jsonValue() == 5

    @sync
    async def test_wait_for_function_window(self):
        assert await self.page.waitForFunction('() => window')

    @sync
    async def test_wait_for_function_arg_element(self):
        await self.page.setContent('<div></div>')
        div = await self.page.J('div')
        fut = asyncio.ensure_future(self.page.waitForFunction('e => !e.parentElement', {}, div))
        fut.add_done_callback(lambda _: self.set_result(True))
        await asyncio.sleep(0.1)
        assert not self.result
        await self.page.evaluate('e => e.remove()', div)
        await fut
        assert self.result

    @sync
    async def test_respect_timeout(self):
        with pytest.raises(TimeoutError) as cm:
            await self.page.waitForFunction('false', {'timeout': 10})
        assert 'Waiting for function failed: timeout' in cm.exception.args[0]

    @sync
    async def test_disable_timeout(self):
        watchdog = self.page.waitForFunction(
            '''() => {
                window.__counter = (window.__counter || 0) + 1;
                return window.__injected;
            }''',
            timeout=0,
            polling=10,
        )
        await self.page.waitForFunction('() => window.__counter > 10')
        await self.page.evaluate('window.__injected = true')
        await watchdog


class TestWaitForSelector(BaseTestCase):
    @sync
    async def test_wait_for_selector_immediate(self):
        frame = self.page.mainFrame
        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('*'))
        fut.add_done_callback(lambda _: result.append(True))
        await fut
        assert result

        result.clear()
        await frame.evaluate(addElement, 'div')
        fut = asyncio.ensure_future(frame.waitForSelector('div'))
        fut.add_done_callback(lambda _: result.append(True))
        await fut
        assert result

    @sync
    async def test_wait_for_selector_after_node_appear(self):
        frame = self.page.mainFrame

        result = []
        fut = asyncio.ensure_future(frame.waitForSelector('div'))
        fut.add_done_callback(lambda _: result.append(True))
        assert await frame.evaluate('() => 42') == 42
        await asyncio.sleep(0.1)
        assert not result
        await frame.evaluate(addElement, 'br')
        await asyncio.sleep(0.1)
        assert not result
        await frame.evaluate(addElement, 'div')
        await fut
        assert result

    @sync
    async def test_wait_for_selector_inner_html(self):
        fut = asyncio.ensure_future(self.page.waitForSelector('h3 div'))
        await self.page.evaluate(addElement, 'span')
        await self.page.evaluate(
            '() => document.querySelector("span").innerHTML = "<h3><div></div></h3>"'
        )  # noqa: E501
        await fut

    @sync
    async def test_shortcut_for_main_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        otherFrame = self.page.frames[1]
        fut = asyncio.ensure_future(self.page.waitForSelector('div'))
        fut.add_done_callback(lambda _: self.set_result(True))
        await otherFrame.evaluate(addElement, 'div')
        await asyncio.sleep(0.1)
        assert not self.result
        await self.page.evaluate(addElement, 'div')
        await fut
        assert self.result

    @sync
    async def test_run_in_specified_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        await attachFrame(self.page, 'frame2', self.url + 'empty')
        frame1 = self.page.frames[1]
        frame2 = self.page.frames[2]
        fut = asyncio.ensure_future(frame2.waitForSelector('div'))
        fut.add_done_callback(lambda _: self.set_result(True))
        await frame1.evaluate(addElement, 'div')
        await asyncio.sleep(0.1)
        assert not self.result
        await frame2.evaluate(addElement, 'div')
        await fut
        assert self.result

    @sync
    async def test_wait_for_selector_fail(self):
        await self.page.evaluate('() => document.querySelector = null')
        with pytest.raises(ElementHandleError):
            await self.page.waitForSelector('*')

    @sync
    async def test_wait_for_page_navigation(self):
        await self.page.goto(self.url + 'empty')
        task = self.page.waitForSelector('h1')
        await self.page.goto(self.url + '1')
        await task

    @sync
    async def test_fail_page_closed(self):
        page = await self.context.newPage()
        await page.goto(self.url + 'empty')
        task = page.waitForSelector('.box')
        await page.close()
        with pytest.raises(NetworkError):
            await task

    @unittest.skip('Cannot catch error.')
    @sync
    async def test_fail_frame_detached(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        frame = self.page.frames[1]
        fut = frame.waitForSelector('.box')
        await detachFrame(self.page, 'frame1')
        with pytest.raises(Exception):
            await fut

    @sync
    async def test_cross_process_navigation(self):
        fut = asyncio.ensure_future(self.page.waitForSelector('h1'))
        fut.add_done_callback(lambda _: self.set_result(True))
        await self.page.goto(self.url + 'empty')
        await asyncio.sleep(0.1)
        assert not self.result
        await self.page.reload()
        await asyncio.sleep(0.1)
        assert not self.result
        await self.page.goto('http://127.0.0.1:{}/'.format(self.port))
        await fut
        assert self.result

    @sync
    async def test_wait_for_selector_visible(self):
        div = []
        fut = asyncio.ensure_future(self.page.waitForSelector('div', visible=True))
        fut.add_done_callback(lambda _: div.append(True))
        await self.page.setContent('<div style="display: none; visibility: hidden;">1</div>')
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await fut
        assert div

    @sync
    async def test_wait_for_selector_visible_inner(self):
        div = []
        fut = asyncio.ensure_future(self.page.waitForSelector('div#inner', visible=True))
        fut.add_done_callback(lambda _: div.append(True))
        await self.page.setContent('<div style="display: none; visibility: hidden;">' '<div id="inner">hi</div></div>')
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("display")')  # noqa: E501
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate('() => document.querySelector("div").style.removeProperty("visibility")')  # noqa: E501
        await fut
        assert div

    @sync
    async def test_wait_for_selector_hidden(self):
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda _: div.append(True))
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate(
            '() => document.querySelector("div").style.setProperty("visibility", "hidden")'
        )  # noqa: E501
        await fut
        assert div

    @sync
    async def test_wait_for_selector_display_none(self):
        div = []
        await self.page.setContent('<div style="display: block;"></div>')
        fut = asyncio.ensure_future(self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda _: div.append(True))
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate(
            '() => document.querySelector("div").style.setProperty("display", "none")'
        )  # noqa: E501
        await fut
        assert div

    @sync
    async def test_wait_for_selector_remove(self):
        div = []
        await self.page.setContent('<div></div>')
        fut = asyncio.ensure_future(self.page.waitForSelector('div', hidden=True))
        fut.add_done_callback(lambda _: div.append(True))
        await asyncio.sleep(0.1)
        assert not div
        await self.page.evaluate('() => document.querySelector("div").remove()')  # noqa: E501
        await fut
        assert div

    @sync
    async def test_wait_for_selector_timeout(self):
        with pytest.raises(TimeoutError) as cm:
            await self.page.waitForSelector('div', timeout=10)
        assert 'Waiting for selector "div" failed: timeout' in cm.exception.args[0]

    @sync
    async def test_error_msg_wait_for_hidden(self):
        await self.page.setContent('<div></div>')
        with pytest.raises(TimeoutError) as cm:
            await self.page.waitForSelector('div', hidden=True, timeout=10)
        assert 'Waiting for selector "div" to be hidden failed: timeout' in cm.exception.args[0]

    @sync
    async def test_wait_for_selector_node_mutation(self):
        div = []
        fut = asyncio.ensure_future(self.page.waitForSelector('.cls'))
        fut.add_done_callback(lambda _: div.append(True))
        await self.page.setContent('<div class="noCls"></div>')
        assert not div
        await self.page.evaluate('() => document.querySelector("div").className="cls"')
        await asyncio.sleep(0.1)
        assert div

    @sync
    async def test_wait_for_selector_return_element(self):
        selector = asyncio.ensure_future(self.page.waitForSelector('.zombo'))
        await self.page.setContent('<div class="zombo">anything</div>')
        assert await self.page.evaluate('e => e.textContent', await selector) == 'anything'


class TestWaitForXPath(BaseTestCase):
    @sync
    async def test_fancy_xpath(self):
        await self.page.setContent('<p>red herring</p><p>hello world  </p>')
        waitForXPath = await self.page.waitForXPath('//p[normalize-space(.)="hello world"]')  # noqa: E501
        assert await self.page.evaluate('x => x.textContent', waitForXPath) == 'hello world  '

    @sync
    async def test_timeout(self):
        with pytest.raises(TimeoutError) as cm:
            await self.page.waitForXPath('//div', timeout=10)
        assert 'Waiting for XPath "//div" failed: timeout' in cm.exception.args[0]

    @sync
    async def test_specified_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        await attachFrame(self.page, 'frame2', self.url + 'empty')
        frame1 = self.page.frames[1]
        frame2 = self.page.frames[2]
        fut = asyncio.ensure_future(frame2.waitForXPath('//div'))
        fut.add_done_callback(lambda _: self.set_result(True))
        assert not self.result
        await frame1.evaluate(addElement, 'div')
        assert not self.result
        await frame2.evaluate(addElement, 'div')
        assert self.result

    @sync
    async def test_evaluation_failed(self):
        await self.page.evaluateOnNewDocument('function() {document.evaluate = null;}')
        await self.page.goto(self.url + 'empty')
        with pytest.raises(ElementHandleError):
            await self.page.waitForXPath('*')

    @unittest.skip('Cannot catch error')
    @sync
    async def test_frame_detached(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        frame = self.page.frames[1]
        waitPromise = frame.waitForXPath('//*[@class="box"]', timeout=1000)
        await detachFrame(self.page, 'frame1')
        with pytest.raises(Exception):
            await waitPromise

    @sync
    async def test_hidden(self):
        await self.page.setContent('<div style="display: block;"></div>')
        waitForXPath = asyncio.ensure_future(self.page.waitForXPath('//div', hidden=True))
        waitForXPath.add_done_callback(lambda _: self.set_result(True))
        await self.page.waitForXPath('//div')
        assert not self.result
        await self.page.evaluate('document.querySelector("div").style.setProperty("display", "none")')  # noqa: E501
        assert await waitForXPath
        assert self.result

    @sync
    async def test_return_element_handle(self):
        waitForXPath = self.page.waitForXPath('//*[@class="zombo"]')
        await self.page.setContent('<div class="zombo">anything</div>')
        assert await self.page.evaluate('x => x.textContent', await waitForXPath) == 'anything'

    @sync
    async def test_text_node(self):
        await self.page.setContent('<div>some text</dev>')
        text = await self.page.waitForXPath('//div/text()')
        assert await (await text.getProperty('nodeType')).jsonValue() == 3

    @sync
    async def test_single_slash(self):
        await self.page.setContent('<div>some text</div>')
        waitForXPath = self.page.waitForXPath('/html/body/div')
        assert await self.page.evaluate('x => x.textContent', await waitForXPath) == 'some text'


class TestFrames(BaseTestCase):
    @sync
    async def test_frame_nested(self):
        await self.page.goto(self.url + 'static/nested-frames.html')
        dumped_frames = dumpFrames(self.page.mainFrame)
        try:
            assert (
                dumped_frames
                == '''
http://localhost:{port}/static/nested-frames.html
    http://localhost:{port}/static/two-frames.html
        http://localhost:{port}/static/frame.html
        http://localhost:{port}/static/frame.html
    http://localhost:{port}/static/frame.html
                '''.format(
                    port=self.port
                ).strip()
            )
        except AssertionError:
            print('\n== Nested frame test failed, which is unstable ==')
            print(dumpFrames(self.page.mainFrame))

    @sync
    async def test_frame_events(self):
        await self.page.goto(self.url + 'empty')
        attachedFrames = []
        self.page.on('frameattached', lambda f: attachedFrames.append(f))
        await attachFrame(self.page, 'frame1', './static/frame.html')
        assert len(attachedFrames) == 1
        assert 'static/frame.html' in attachedFrames[0].url

        navigatedFrames = []
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await navigateFrame(self.page, 'frame1', '/empty')
        assert len(navigatedFrames) == 1
        assert 'empty' in navigatedFrames[0].url

        detachedFrames = []
        self.page.on('framedetached', lambda f: detachedFrames.append(f))
        await detachFrame(self.page, 'frame1')
        assert len(detachedFrames) == 1
        assert detachedFrames[0].isDetached()

    @sync
    async def test_anchor_url(self):
        await self.page.goto(self.url + 'empty')
        await asyncio.wait(
            [self.page.goto(self.url + 'empty#foo'), waitEvent(self.page, 'framenavigated'),]
        )
        assert self.page.url == self.url + 'empty#foo'

    @sync
    async def test_frame_cross_process(self):
        await self.page.goto(self.url + 'empty')
        mainFrame = self.page.mainFrame
        await self.page.goto('http://127.0.0.1:{}/empty'.format(self.port))
        assert self.page.mainFrame == mainFrame

    @sync
    async def test_frame_events_main(self):
        # no attach/detach events should be emitted on main frame
        events = []
        navigatedFrames = []
        self.page.on('frameattached', lambda f: events.append(f))
        self.page.on('framedetached', lambda f: events.append(f))
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await self.page.goto(self.url + 'empty')
        assert not events
        assert len(navigatedFrames) == 1

    @sync
    async def test_frame_events_child(self):
        attachedFrames = []
        detachedFrames = []
        navigatedFrames = []
        self.page.on('frameattached', lambda f: attachedFrames.append(f))
        self.page.on('framedetached', lambda f: detachedFrames.append(f))
        self.page.on('framenavigated', lambda f: navigatedFrames.append(f))
        await self.page.goto(self.url + 'static/nested-frames.html')
        assert len(attachedFrames) == 4
        assert len(detachedFrames) == 0
        assert len(navigatedFrames) == 5

        attachedFrames.clear()
        detachedFrames.clear()
        navigatedFrames.clear()
        await self.page.goto(self.url + 'empty')
        assert len(attachedFrames) == 0
        assert len(detachedFrames) == 4
        assert len(navigatedFrames) == 1

    @sync
    async def test_frame_name(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'FrameId', self.url + 'empty')
        await asyncio.sleep(0.1)
        await self.page.evaluate(
            '''(url) => {
                const frame = document.createElement('iframe');
                frame.name = 'FrameName';
                frame.src = url;
                document.body.appendChild(frame);
                return new Promise(x => frame.onload = x);
            }''',
            self.url + 'empty',
        )
        await asyncio.sleep(0.1)

        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        frame3 = self.page.frames[2]
        assert frame1.name == ''
        assert frame2.name == 'FrameId'
        assert frame3.name == 'FrameName'

    @sync
    async def test_frame_parent(self):
        await self.page.goto(self.url + 'empty')
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        await attachFrame(self.page, 'frame2', self.url + 'empty')
        frame1 = self.page.frames[0]
        frame2 = self.page.frames[1]
        frame3 = self.page.frames[2]
        assert frame1 == self.page.mainFrame
        assert frame1.parentFrame == None
        assert frame2.parentFrame == frame1
        assert frame3.parentFrame == frame1
