#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

import pytest
from pyppeteer import connect
from pyppeteer.errors import BrowserError
from syncer import sync
from tests.utils import gather_with_timeout, waitEvent


@sync
async def test_default_context(shared_browser):
    assert len(shared_browser.browserContexts) == 1
    defaultContext = shared_browser.browserContexts[0]
    assert not defaultContext.isIncognito()
    with pytest.raises(BrowserError, match='cannot be closed') as cm:
        await defaultContext.close()


@sync
async def test_incognito_context(shared_browser):
    assert len(shared_browser.browserContexts) == 1
    context = await shared_browser.createIncognitoBrowserContext()
    assert context.isIncognito()
    assert len(shared_browser.browserContexts) == 2
    assert context in shared_browser.browserContexts
    await context.close()
    assert len(shared_browser.browserContexts) == 1


@sync
async def test_close_all_targets_on_closing_context(shared_browser):
    assert len(await shared_browser.pages) == 1
    context = await shared_browser.createIncognitoBrowserContext()
    await context.newPage()
    assert len(await shared_browser.pages) == 2
    assert len(await context.pages()) == 1
    await context.close()
    assert len(await shared_browser.pages) == 1


@sync
async def test_window_open_use_parent_tab_context(shared_browser, server):
    context = await shared_browser.createIncognitoBrowserContext()
    page = await context.newPage()
    await page.goto(server.empty_page)
    asyncio.create_task(page.evaluate('url => window.open(url)', server.empty_page))
    popupTarget = await waitEvent(shared_browser, 'targetcreated')
    assert popupTarget.browserContext == context
    await context.close()


@sync
async def test_fire_target_event(server, shared_browser):
    context = await shared_browser.createIncognitoBrowserContext()
    events = []
    context.on('targetcreated', lambda t: events.append('CREATED: ' + t.url))
    context.on('targetchanged', lambda t: events.append('CHANGED: ' + t.url))
    context.on('targetdestroyed', lambda t: events.append('DESTROYED: ' + t.url))
    page = await context.newPage()
    await page.goto(server.empty_page)
    await page.close()
    assert events == [
        'CREATED: about:blank',
        f'CHANGED: {server.empty_page}',
        f'DESTROYED: {server.empty_page}',
    ]


@sync
async def test_isolate_local_storage_and_cookie(shared_browser, server):
    context1 = await shared_browser.createIncognitoBrowserContext()
    context2 = await shared_browser.createIncognitoBrowserContext()
    assert len(context1.targets()) == 0
    assert len(context2.targets()) == 0

    # create a page in the first incognito context
    page1 = await context1.newPage()
    await page1.goto(server.empty_page)
    await page1.evaluate(
        '''() => {
        localStorage.setItem('name', 'page1');
        document.cookie = 'name=page1';
    }'''
    )

    assert len(context1.targets()) == 1
    assert len(context2.targets()) == 0

    # create a page in the second incognito context
    page2 = await context2.newPage()
    await page2.goto(server.empty_page)
    await page2.evaluate(
        '''() => {
        localStorage.setItem('name', 'page2');
        document.cookie = 'name=page2';
    }'''
    )

    assert len(context1.targets()) == 1
    assert context1.targets()[0] == page1.target
    assert len(context2.targets()) == 1
    assert context2.targets()[0] == page2.target

    # make sure pages don't share local storage and cookie
    assert await page1.evaluate('localStorage.getItem("name")') == 'page1'
    assert await page1.evaluate('document.cookie') == 'name=page1'
    assert await page2.evaluate('localStorage.getItem("name")') == 'page2'
    assert await page2.evaluate('document.cookie') == 'name=page2'

    await gather_with_timeout(context1.close(), context2.close())
    assert len(shared_browser.browserContexts) == 1


@sync
async def test_across_session(shared_browser):
    assert len(shared_browser.browserContexts) == 1
    context = await shared_browser.createIncognitoBrowserContext()
    assert len(shared_browser.browserContexts) == 2
    remoteBrowser = await connect(browserWSEndpoint=shared_browser.wsEndpoint)
    contexts = remoteBrowser.browserContexts
    assert len(contexts) == 2
    await remoteBrowser.disconnect()
    await context.close()
