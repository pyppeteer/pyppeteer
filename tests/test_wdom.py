#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
import unittest

from syncer import sync

from wdom.document import get_document, get_new_document, set_document
from wdom.examples import data_binding, drag, rev_text
from wdom.server import start_server, stop_server, server_config
from wdom.util import suppress_logging

from pyppeteer import launch


def setUpModule():
    suppress_logging()
    global browser, page
    browser = launch(args=['--no-sandbox'])
    page = sync(browser.newPage())


def tearDownModule():
    sync(browser.close())


class TestBase(unittest.TestCase):
    app = None  # type: Callable[[], Tag]

    def setUp(self):
        self.doc = get_document()
        self.doc.body.appendChild(self.app())
        self.server = start_server(port=0)
        self.addr = server_config['address']
        self.port = server_config['port']
        self.url = 'http://{}:{}/'.format(self.addr, self.port)
        self.page = page
        sync(self.page.goto(self.url))

    def tearDown(self):
        stop_server(self.server)
        set_document(get_new_document())
        sync(self.page.goto('about:blank'))
        time.sleep(0.1)

    async def wait(self, timeout=0.1):
        await asyncio.sleep(timeout)


class TestClick(TestBase):
    app = staticmethod(rev_text.sample_app)

    @sync
    async def test_click(self):
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Click!')
        await self.page.click('h1')
        await self.page.waitForFunction(
            '() => document.body.textContent.indexOf("!kcilC") >= 0',
            {'timeout': 1000},
        )
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Click!'[::-1])


class TestInput(TestBase):
    app = staticmethod(data_binding.sample_app)

    @sync
    async def test_keyboard_sendchar(self):
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Hello!')
        await self.page.focus('input')
        await self.page.keyboard.sendCharacter('abc')
        await self.page.waitForFunction(
            '() => document.body.textContent.indexOf("abc") >= 0',
            {'timeout': 1000},
        )
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'abc')

    @sync
    async def test_page_type(self):
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Hello!')
        await self.page.focus('input')
        await self.page.type('abc', {})
        await self.page.waitForFunction(
            '() => document.body.textContent.indexOf("abc") >= 0',
            {'timeout': 1000},
        )
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'abc')


class TestDrag(TestBase):
    app = staticmethod(drag.sample_app)

    @sync
    async def test_click(self):
        mouse = self.page.mouse
        _from = await self.page.J('[id="1"]')
        _to = await self.page.J('[id="2"]')
        _from_c = await _from._visibleCenter()
        _to_c = await _to._visibleCenter()
        start = (_from_c['x'], _from_c['y'])
        end = (_to_c['x'], _to_c['y'])
        await mouse.move(*start)
        await self.wait()
        await mouse.down()
        await self.wait()
        await mouse.move(*end, steps=50)
        await mouse.up()
        await self.wait()
