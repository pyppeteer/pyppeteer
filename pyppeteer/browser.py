#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from typing import Callable

from pyppeteer.connection import Connection
from pyppeteer.page import Page, create_page


class Browser(object):
    def __init__(self, connection: Connection, ignoreHTTPSErrors: bool,
                 closeCallback: Callable[[], None]) -> None:
        self._connection = connection
        self._ignoreHTTPSErrors = ignoreHTTPSErrors
        self._closeCallback = closeCallback

    async def newPage(self) -> Page:
        targetId = (await self._connection.send(
            'Target.createTarget',
            {'url': 'about:blank'})).get('targetId')
        client = await self._connection.createSession(targetId)
        page = await create_page(client)
        return page

    def close(self) -> None:
        asyncio.get_event_loop().run_until_complete(self._connection.dispose())
        self._closeCallback()
