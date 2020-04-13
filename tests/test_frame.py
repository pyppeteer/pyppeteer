#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from asyncio import gather

import pytest
from syncer import sync

from pyppeteer.errors import BrowserError
from tests.utils import waitEvent, attachFrame, detachFrame, dumpFrames, navigateFrame


@sync
async def test_executionContext(isolated_page, server):
    p = isolated_page
    await p.goto(server.empty_page)
    await attachFrame(p, server.empty_page, 'frame1')
    assert len(p.frames) == 2

    frame1, frame2 = p.frames
    context1 = await frame1.executionContext
    context2 = await frame2.executionContext
    assert context1.frame is frame1
    assert context2.frame is frame2

    await gather(
        context1.evaluate('window.a = 1'),
        context2.evaluate('window.a = 2'),
    )
    a1, a2 = await gather(
        context1.evaluate('window.a'),
        context2.evaluate('window.a'),
    )
    assert a1 == 1
    assert a2 == 2

@sync
async def test_evaluate(isolated_page, server):
    p = isolated_page
    # should throw for detached frames
    frame1 = await attachFrame(p, server.empty_page, 'frame1')
    await detachFrame(p, 'frame1')
    with pytest.raises(BrowserError) as e:
        await frame1.evaluate('7 * 8')
    assert e.match('Execution Context is not available in detached frame')

@sync
async def test_management(isolated_page, server):
    p = isolated_page
    await p.goto(server / 'frames/nested-frames.html')
    assert dumpFrames(p.mainFrame) == [
        server / 'frames/nested-frames.html',
        '    ' + server / 'frames/two-frames.html (2frames)',
        '        ' + server / 'frames/frame.html (uno)',
        '        ' + server / 'frames/frame.html (dos)',
        '    ' + server / 'frames/frame.html (aframe)',
    ]

    # should send events when frames are manipulated dynamically
    await p.goto(server.empty_page)
    # validate frameattached events
    attachedFrames = []
    p.on('frameattached', lambda frame: attachedFrames.append(frame))
    await attachFrame(p, 'assets/frame.html', 'frame1')
    assert attachedFrames
    assert 'assets/frame.html' in attachedFrames[0].url
    # validated framenavigated events
    navigatedFrames = []
    p.on('framenavigated', lambda frame: navigatedFrames.append(frame))
    await navigateFrame(p, 'frame1', 'empty.html')
    assert navigatedFrames
    assert 'empty.html' in navigatedFrames[0].url
    # validate framedetached events
    detachedFrames = []
    p.on('framedetached', lambda frame: detachedFrames.append(frame))
    await detachFrame(p, 'frame1')
    assert len(detachedFrames) == 1
    assert detachedFrames[0].isDetached is True
    # should send framenavigated when navigating on anchor urls
    await p.goto(server.empty_page)
    await gather(
        p.goto(server.empty_page + '#foo'),
        waitEvent(p, 'framenavigated')
    )
    assert p.url == server.empty_page + '#foo'
    # should persist mainFrame on cross-process navigation
    await p.goto(server.empty_page)
    mainFrame = p.mainFrame
    await p.goto(server.cross_process_server / 'empty.html')
    assert p.mainFrame is mainFrame

@sync
async def test_attaching(isolated_page, server):
    p = isolated_page
    # should detach child frames on navigation
    attachedFrames = []
    detachedFrames = []
    navigatedFrames = []
    p.on('frameattached', lambda frame: attachedFrames.append(frame))
    p.on('framedetached', lambda frame: detachedFrames.append(frame))
    p.on('framenavigated', lambda frame: navigatedFrames.append(frame))
    await p.goto(server / 'frames/nested-frames.html')
    assert len(attachedFrames) == 4
    assert len(detachedFrames) == 0
    assert len(navigatedFrames) == 5

    # should detach child frames on navigation
    attachedFrames = []
    detachedFrames = []
    navigatedFrames = []
    await p.goto(server.empty_page)
    assert len(attachedFrames) == 0
    # TODO here detachedframes has more than 4 because it's filled with dupes
    assert len(detachedFrames) == 4
    assert len(navigatedFrames) == 1

@sync
async def test_report_frame(isolated_page, server):
    p = isolated_page
    # should report frame from-inside shadow DOM
    await p.goto(server / 'shadow.html')
    await p.evaluate(
        """
        async url => {
            const frame = document.createElement('iframe');
            frame.src = url;
            document.body.shadowRoot.appendChild(frame);
            await new Promise(x => frame.onload = x);
        }
        """,
        server.empty_page
    )
    assert len(p.frames) == 2
    assert p.frames[1].url == server.empty_page

@sync
async def test_report_frame_name(isolated_page, server):
    p = isolated_page
    await attachFrame(p, server.empty_page, 'theFrameId')
    await p.evaluate(
        """
        url => {
            const frame = document.createElement('iframe');
            frame.name = 'theFrameName';
            frame.src = url;
            document.body.appendChild(frame);
            return new Promise(x => frame.onload = x);
        }
        """,
        server.empty_page
    )
    assert p.frames[0].name == ''
    assert p.frames[1].name == 'theFrameId'
    assert p.frames[2].name == 'theFrameName'

@sync
async def test_report_frame_parents(isolated_page, server):
    p = isolated_page
    await attachFrame(p, server.empty_page, 'frame1')
    await attachFrame(p, server.empty_page, 'frame2')
    assert p.frames[0].parentFrame is None
    assert p.frames[1].parentFrame is p.mainFrame
    assert p.frames[2].parentFrame is p.mainFrame

@sync
async def test_frame_reattach(isolated_page, server):
    p = isolated_page
    frame1 = await attachFrame(p, server.empty_page, 'frame1')
    await p.evaluate(
        """
        () => {
            window.frame = document.querySelector('#frame1');
            window.frame.remove();
        }
        """
    )
    assert frame1.isDetached is True
    frame2 = (await gather(
        waitEvent(p, 'frameattached'),
        p.evaluate('document.body.appendChild(window.frame)')
    ))[0]
    assert frame2.isDetached is False
    assert frame1 is not frame2

