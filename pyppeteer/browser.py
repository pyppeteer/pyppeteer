#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Browser module."""

import asyncio
from subprocess import Popen
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pyee import EventEmitter

from pyppeteer.connection import Connection, CDPSession
from pyppeteer.errors import BrowserError
from pyppeteer.page import Page
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
        target = Target(self, event['targetInfo'])
        if event['targetInfo']['targetId'] in self._targets:
            raise BrowserError('target should not exist before create.')
        self._targets[event['targetInfo']['targetId']] = target
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
        target._targetInfoChanged(event['targetInfo'])

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


class Target(object):
    """Browser's target class."""

    def __init__(self, browser: Browser, targetInfo: Dict) -> None:
        self._browser = browser
        self._targetId = targetInfo.get('targetId', '')
        self._targetInfo = targetInfo
        self._page = None

        self._initializedPromise = asyncio.get_event_loop().create_future()
        self._isInitialized = (self._targetInfo['type'] != 'page'
                               or self._targetInfo['url'] != '')
        if self._isInitialized:
            self._initializedCallback(True)

    def _initializedCallback(self, bl: bool) -> None:
        # TODO: this may cause error on page close
        if self._initializedPromise.done():
            self._initializedPromise = asyncio.get_event_loop().create_future()
        self._initializedPromise.set_result(bl)

    async def createCDPSession(self) -> CDPSession:
        """Create a Chrome Devtools Protocol session attached to the target."""
        return await self._browser._connection.createSession(self._targetId)

    async def page(self) -> Optional[Page]:
        """Get page of this target."""
        if self._targetInfo['type'] == 'page' and self._page is None:
            client = await self._browser._connection.createSession(
                self._targetId)
            new_page = await Page.create(
                client, self,
                self._browser._ignoreHTTPSErrors,
                self._browser._appMode,
                self._browser._screenshotTaskQueue,
            )
            self._page = new_page
            return new_page
        return self._page

    @property
    def url(self) -> str:
        """Get url of this target."""
        return self._targetInfo['url']

    @property
    def type(self) -> str:
        """Get type of this target."""
        _type = self._targetInfo['type']
        if _type == 'page' or _type == 'service_worker':
            return _type
        return 'other'

    def _targetInfoChanged(self, targetInfo: Dict) -> None:
        previousURL = self._targetInfo['url']
        self._targetInfo = targetInfo

        if not self._isInitialized and (self._targetInfo['type'] != 'page' or
                                        self._targetInfo['url'] != ''):
            self._isInitialized = True
            self._initializedCallback(True)
            return

        if previousURL != targetInfo['url']:
            self._browser.emit(Browser.Events.TargetChanged, self)
