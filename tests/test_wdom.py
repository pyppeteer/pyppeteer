#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest

from syncer import sync

from wdom.document import get_document, get_new_document, set_document
from wdom.examples import data_binding, drag, rev_text
from wdom.server import start_server, stop_server, server_config
from wdom.tag import Tag
from wdom.util import suppress_logging

from pyppeteer.launcher import launch


def setUpModule():
    suppress_logging()


class TestBase(unittest.TestCase):
    app: Tag

    def setUp(self):
        self.doc = get_document()
        self.doc.body.appendChild(self.app)
        self.server = start_server(port=0)
        self.addr = server_config['address']
        self.port = server_config['port']
        self.url = f'http://{self.addr}:{self.port}/'
        self.browser = launch({'headless': True})
        self.page = sync(self.browser.newPage())
        sync(self.page.goto(self.url))

    def tearDown(self):
        stop_server(self.server)
        set_document(get_new_document())

    async def wait(self, timeout=0.1):
        await asyncio.sleep(timeout)


class TestClick(TestBase):
    app = rev_text.sample_app()

    @sync
    async def test_click(self):
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Click!')
        await self.page.click('h1')
        await self.wait()
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Click!'[::-1])


class TestInput(TestBase):
    app = data_binding.sample_app()

    @sync
    async def test_click(self):
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'Hello!')
        await self.page.focus('input')
        await self.wait()
        await self.page.keyboard.sendCharacter('abc')
        await self.wait()
        text = await self.page.plainText()
        self.assertEqual(text.strip(), 'abc')


class TestDrag(TestBase):
    app = drag.sample_app()

    @sync
    async def test_click(self):
        mouse = self.page.mouse
        await self.page.hover('[id="1"]')
        await self.wait()
        await mouse.down()
        await self.wait()
        await self.page.hover('[id="2"]')
        await self.wait()
        await mouse.up()
        await self.wait()
