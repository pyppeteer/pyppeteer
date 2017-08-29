#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pyppeteer
----------------------------------

Tests for `pyppeteer` module.
"""

import asyncio
import logging
from unittest import TestCase

from syncer import sync
from tornado import web

from pyppeteer.launcher import launch
from pyppeteer.util import install_asyncio, get_free_port


def setUpModule() -> None:
    logging.getLogger('tornado').setLevel(logging.ERROR)
    # logging.getLogger('pyppeteer').setLevel(logging.ERROR)
    install_asyncio()


BASE_HTML = '''
<html>
<head><title>main</title></head>
<body>
<h1 id="hello">Hello</h1>
<a id="link1" href="./1">link1</a>
<a id="link2" href="./2">link2</a>
</body>
</html>
'''


class MainHandler(web.RequestHandler):
    def get(self) -> None:
        self.write(BASE_HTML)


class LinkHandler1(web.RequestHandler):
    def get(self) -> None:
        self.write('''
<head><title>link1</title></head>
<h1 id="link1">Link1</h1>
<a id="back1" href="./">back1</a>
        ''')


class TestPyppeteer(TestCase):
    def setUp(self):
        self.port = get_free_port()
        self.app = web.Application([
            ('/', MainHandler),
            ('/1', LinkHandler1),
        ], logging='error')
        self.server = self.app.listen(self.port)
        self.browser = launch()

    @sync
    async def test_get(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        self.assertEqual(await self.page.title(), 'main')
        self.elm = await self.page.querySelector('h1#hello')
        self.assertTrue(self.elm)

    @sync
    async def test_plain_text(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        text = await self.page.plainText()
        self.assertEqual(text.split(), ['Hello', 'link1', 'link2'])

    @sync
    async def test_html(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        html = await self.page.html()
        self.assertEqual(html.replace('\n', ''), BASE_HTML.replace('\n', ''))

    @sync
    async def test_click(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        await self.page.click('#link1')
        await asyncio.sleep(0.1)
        self.assertEqual(await self.page.title(), 'link1')
        elm = await self.page.querySelector('h1#link1')
        self.assertTrue(elm)

    @sync
    async def test_elm_click(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        btn1 = await self.page.querySelector('#link1')
        self.assertTrue(btn1)
        await btn1.click()
        await asyncio.sleep(0.1)
        self.assertEqual(await self.page.title(), 'link1')

    @sync
    async def test_back_forward(self):
        self.page = await self.browser.newPage()
        await self.page.goto('http://localhost:' + str(self.port))
        await self.page.click('#link1')
        await asyncio.sleep(0.1)
        self.assertEqual(await self.page.title(), 'link1')
        await self.page.goBack()
        await asyncio.sleep(0.1)
        self.assertEqual(await self.page.title(), 'main')
        elm = await self.page.querySelector('h1#hello')
        self.assertTrue(elm)
        await self.page.goForward()
        await asyncio.sleep(0.1)
        self.assertEqual(await self.page.title(), 'link1')
        btn2 = await self.page.querySelector('#link1')
        self.assertTrue(btn2)

    def tearDown(self):
        self.browser.close()
        self.server.stop()
