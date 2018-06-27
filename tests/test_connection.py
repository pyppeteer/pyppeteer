#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import NetworkError

from .base import BaseTestCase


class TestConnection(BaseTestCase):
    @sync
    async def test_error_msg(self):
        with self.assertRaises(NetworkError) as cm:
            await self.page._client.send('ThisCommand.DoesNotExists')
        self.assertIn('ThisCommand.DoesNotExists', cm.exception.args[0])


class TestCDPSession(BaseTestCase):
    @sync
    async def test_create_session(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        await client.send('Runtime.evaluate',
                          {'expression': 'window.foo = "bar"'})
        foo = await self.page.evaluate('window.foo')
        self.assertEqual(foo, 'bar')

    @sync
    async def test_send_event(self):
        client = await self.page.target.createCDPSession()
        await client.send('Network.enable')
        events = []
        client.on('Network.requestWillBeSent', lambda e: events.append(e))
        await self.page.goto(self.url + 'empty')
        self.assertEqual(len(events), 1)

    @sync
    async def test_enable_disable_domain(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        await client.send('Debugger.enable')
        await self.page.coverage.startJSCoverage()
        await self.page.coverage.stopJSCoverage()

    @sync
    async def test_detach(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        evalResponse = await client.send(
            'Runtime.evaluate', {'expression': '1 + 2', 'returnByValue': True})
        self.assertEqual(evalResponse['result']['value'], 3)

        await client.detach()
        with self.assertRaises(NetworkError):
            await client.send(
                'Runtime.evaluate',
                {'expression': '1 + 3', 'returnByValue': True}
            )
