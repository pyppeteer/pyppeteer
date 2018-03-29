#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import NetworkError

from base import BaseTestCase


class TestConnection(BaseTestCase):
    @sync
    async def test_error_msg(self):
        with self.assertRaises(NetworkError) as cm:
            await self.page._client.send('ThisCommand.DoesNotExists')
        self.assertIn('ThisCommand.DoesNotExists', cm.exception.args[0])
