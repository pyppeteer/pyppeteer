#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest
from typing import Callable

from syncer import sync

from wdom.document import get_document, get_new_document, set_document
from wdom.examples import data_binding, drag, rev_text
from wdom.server import start_server, stop_server, server_config
from wdom.tag import Tag
from wdom.util import suppress_logging

from pyppeteer.launcher import launch


def setUpModule():
    suppress_logging()
    global browser, page
    browser = launch({'headless': True})
    page = sync(browser.newPage())


def tearDownModule():
    browser.close()


class TestBase(unittest.TestCase):
    app: Callable[[], Tag]

    def setUp(self):
        self.doc = get_document()
        self.doc.body.appendChild(self.app())
        self.server = start_server(port=0)
        self.addr = server_config['address']
        self.port = server_config['port']
        self.url = f'http://{self.addr}:{self.port}/'
        self.page = page
        sync(self.page.goto(self.url))

    def tearDown(self):
        stop_server(self.server)
        set_document(get_new_document())
        sync(self.page.goto('about:blank'))

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
        await self.page.hover('[id="1"]')
        await mouse.down()
        await self.page.hover('[id="2"]')
        await mouse.up()
        await self.wait()
