#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Browser module."""

from typing import Awaitable, Callable, Dict

from pyppeteer.connection import Connection
from pyppeteer.page import Page


class Browser(object):
    """Browser class."""

    def __init__(self, connection: Connection, options: Dict = None,
                 closeCallback: Callable[[], Awaitable[None]] = None) -> None:
        """Make new browser object."""
        if options is None:
            options = {}
        self._connection = connection
        self._ignoreHTTPSErrors = bool(options.get('ignoreHTTPSErrors', False))
        if closeCallback is None:
            raise TypeError('`closeCallback` is required.')
        self._closeCallback = closeCallback

    @property
    def wsEndpoint(self) -> str:
        """Retrun websocket endpoint url."""
        return self._connection.url

    async def newPage(self) -> Page:
        """Make new page on browser and return it."""
        targetId = (await self._connection.send(
            'Target.createTarget',
            {'url': 'about:blank'})).get('targetId')
        client = await self._connection.createSession(targetId)
        page = await Page.create(client)
        return page

    async def close(self) -> None:
        """Close connections and terminate browser process."""
        await self._closeCallback()
        await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect browser."""
        await self._connection.dispose()
