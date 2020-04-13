#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import NetworkError

from .base import BaseTestCase
import pytest


class TestConnection(BaseTestCase):
    @sync
    async def test_error_msg(self):
        with pytest.raises(NetworkError, match='ThisCommand.DoesNotExists') as cm:
            await self.page._client.send('ThisCommand.DoesNotExists')


class TestCDPSession(BaseTestCase):
    @sync
    async def test_create_session(self):
        client = await self.page.target.createCDPSession()
        await client.send('Runtime.enable')
        await client.send('Runtime.evaluate', {'expression': 'window.foo = "bar"'})
        foo = await self.page.evaluate('window.foo')
        assert foo == 'bar'

    @sync
    async def test_send_event(self):
        client = await self.page.target.createCDPSession()
        await client.send('Network.enable')
        events = []
        client.on('Network.requestWillBeSent', lambda e: events.append(e))
        await self.page.goto(self.url + 'empty')
        assert len(events) == 1

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
        evalResponse = await client.send('Runtime.evaluate', {'expression': '1 + 2', 'returnByValue': True})
        assert evalResponse['result']['value'] == 3

        await client.detach()
        with pytest.raises(NetworkError):
            await client.send('Runtime.evaluate', {'expression': '1 + 3', 'returnByValue': True})
