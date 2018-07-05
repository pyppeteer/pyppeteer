#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Browser module."""

import asyncio
from subprocess import Popen
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pyee import EventEmitter

from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.page import Page
from pyppeteer.target import Target
from pyppeteer.util import merge_dict


class Browser(EventEmitter):
    """Browser class.

    A Broser object is created when pyppeteer connects to chrome, either
    through :func:`~pyppeteer.launcer.launch` or
    :func:`~pyppeteer.launcer.connect`.
    """

    Events = SimpleNamespace(
        TargetCreated='targetcreated',
        TargetDestroyed='targetdestroyed',
        TargetChanged='targetchanged',
        Disconnected='disconnected',
    )

    def __init__(self, connection: Connection, options: Dict = None,
                 process: Optional[Popen] = None,
                 closeCallback: Callable[[], Awaitable[None]] = None,
                 **kwargs: Any) -> None:
        super().__init__()
        options = merge_dict(options, kwargs)
        self._ignoreHTTPSErrors = bool(options.get('ignoreHTTPSErrors', False))
        self._appMode = bool(options.get('appMode', False))
        self._process = process
        self._screenshotTaskQueue: List = []
        self._connection = connection

        def _dummy_callback() -> Awaitable[None]:
            fut = asyncio.get_event_loop().create_future()
            fut.set_result(None)
            return fut

        if closeCallback:
            self._closeCallback = closeCallback
        else:
            self._closeCallback = _dummy_callback
        self._targets: Dict[str, Target] = dict()
        self._connection.setClosedCallback(
            lambda: self.emit(Browser.Events.Disconnected)
        )
        self._connection.on('Target.targetCreated', self._targetCreated)
        self._connection.on('Target.targetDestroyed', self._targetDestroyed)
        self._connection.on('Target.targetInfoChanged', self._targetInfoChanged)  # noqa: E501

    @property
    def process(self) -> Optional[Popen]:
        """Return process of this browser.

        If browser instance is created by :func:`pyppeteer.launcer.connect`,
        return ``None``.
        """
        return self._process

    @staticmethod
    async def create(connection: Connection, options: dict = None,
                     process: Optional[Popen] = None,
                     closeCallback: Callable[[], Awaitable[None]] = None,
                     **kwargs: Any) -> 'Browser':
        """Create browser object."""
        options = merge_dict(options, kwargs)
        browser = Browser(connection, options, process, closeCallback)
        await connection.send('Target.setDiscoverTargets', {'discover': True})
        return browser

    async def _targetCreated(self, event: Dict) -> None:
        targetInfo = event['targetInfo']
        target = Target(
            targetInfo,
            lambda: self._connection.createSession(targetInfo['targetId']),
            self._ignoreHTTPSErrors,
            self._appMode,
            self._screenshotTaskQueue,
        )
        if targetInfo['targetId'] in self._targets:
            raise BrowserError('target should not exist before create.')
        self._targets[targetInfo['targetId']] = target
        if await target._initializedPromise:
            self.emit(Browser.Events.TargetCreated, target)

    async def _targetDestroyed(self, event: Dict) -> None:
        target = self._targets[event['targetId']]
        del self._targets[event['targetId']]
        if await target._initializedPromise:
            self.emit(Browser.Events.TargetDestroyed, target)
        target._initializedCallback(False)

    async def _targetInfoChanged(self, event: Dict) -> None:
        target = self._targets.get(event['targetInfo']['targetId'])
        if not target:
            raise BrowserError('target should exist before targetInfoChanged')
        previousURL = target.url
        wasInitialized = target._isInitialized
        target._targetInfoChanged(event['targetInfo'])
        if wasInitialized and previousURL != target.url:
            self.emit(Browser.Events.TargetChanged, target)

    @property
    def wsEndpoint(self) -> str:
        """Retrun websocket end point url."""
        return self._connection.url

    async def newPage(self) -> Page:
        """Make new page on this browser and return its object."""
        targetId = (await self._connection.send(
            'Target.createTarget',
            {'url': 'about:blank'})).get('targetId')
        target = self._targets.get(targetId)
        if target is None:
            raise BrowserError('Failed to create target for page.')
        if not await target._initializedPromise:
            raise BrowserError('Failed to create target for page.')
        page = await target.page()
        if page is None:
            raise BrowserError('Failed to create page.')
        return page

    def targets(self) -> List['Target']:
        """Get all targets of this browser."""
        return [target for target in self._targets.values()
                if target._isInitialized]

    async def pages(self) -> List[Page]:
        """Get all pages of this browser."""
        pages = []
        for target in self.targets():
            page = await target.page()
            if page:
                pages.append(page)
        return pages

    async def version(self) -> str:
        """Get version of the browser."""
        version = await self._getVersion()
        return version['product']

    async def userAgent(self) -> str:
        """Return browser's original user agent.

        .. note::
            Pages can override browser user agent with
            :meth:`pyppeteer.page.Page.setUserAgent`.
        """
        version = await self._getVersion()
        return version.get('userAgent', '')

    async def close(self) -> None:
        """Close connections and terminate browser process."""
        await self._closeCallback()  # Launcher.killChrome()

    async def disconnect(self) -> None:
        """Disconnect browser."""
        await self._connection.dispose()

    def _getVersion(self) -> Awaitable:
        return self._connection.send('Browser.getVersion')
