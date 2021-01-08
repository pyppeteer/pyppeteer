#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Browser module."""
import asyncio
import logging
from asyncio import Future
from subprocess import Popen
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional, Sequence

from pyee import AsyncIOEventEmitter
from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.events import Events
from pyppeteer.models import Protocol, WebPermission
from pyppeteer.target import Target
from pyppeteer.task_queue import TaskQueue

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pyppeteer.page import Page


class Browser(AsyncIOEventEmitter):
    """Browser class.

    A Browser object is created when pyppeteer connects to chrome, either
    through :func:`~pyppeteer.launcher.launch` or
    :func:`~pyppeteer.launcher.connect`.
    """

    def __init__(
        self,
        connection: Connection,
        contextIds: List[str],
        ignoreHTTPSErrors: bool,
        defaultViewport: Protocol.Page.Viewport,
        process: Optional[Popen] = None,
        closeCallback: Callable[[], Awaitable[None]] = None,
    ) -> None:
        super().__init__()
        self._ignoreHTTPSErrors = ignoreHTTPSErrors
        self._defaultViewport = defaultViewport
        self._process = process
        self._screenshotTaskQueue = TaskQueue()
        self._connection = connection
        self.loop = self._connection.loop

        if closeCallback:
            self._closeCallback = closeCallback
        else:

            async def _dummy_callback() -> None:
                pass

            self._closeCallback = _dummy_callback

        self._defaultContext = BrowserContext(self._connection, self, None)
        self._contexts: Dict[str, BrowserContext] = {}
        for contextId in contextIds:
            self._contexts[contextId] = BrowserContext(self._connection, self, None)

        self._targets: Dict[str, Target] = {}
        self._connection.on(Events.Connection.Disconnected, lambda: self.emit(Events.Browser.Disconnected))
        self._connection.on(
            'Target.targetCreated', lambda event: self.loop.create_task(self._targetCreated(event)),
        )
        self._connection.on(
            'Target.targetDestroyed', lambda event: self.loop.create_task(self._targetDestroyed(event)),
        )
        self._connection.on(
            'Target.targetInfoChanged', lambda event: self.loop.create_task(self._targetInfoChanged(event)),
        )

    @property
    def process(self) -> Optional[Popen]:
        """Return process of this browser.

        If browser instance is created by :func:`pyppeteer.launcher.connect`,
        return ``None``.
        """
        return self._process

    async def createIncognitoBrowserContext(self) -> 'BrowserContext':
        """Create a new incognito browser context.

        This won't share cookies/cache with other browser contexts.

        .. code::

            browser = await launch()
            # Create a new incognito browser context.
            context = await browser.createIncognitoBrowserContext()
            # Create a new page in a pristine context.
            page = await context.newPage()
            # Do stuff
            await page.goto('https://example.com')
            ...
        """
        obj = await self._connection.send('Target.createBrowserContext')
        browserContextId = obj['browserContextId']
        context = BrowserContext(self._connection, self, browserContextId)
        self._contexts[browserContextId] = context
        return context

    @property
    def browserContexts(self) -> List['BrowserContext']:
        """Return a list of all open browser contexts.

        In a newly created browser, this will return a single instance of
        ``[BrowserContext]``
        """
        return [self._defaultContext] + [context for context in self._contexts.values()]

    @property
    def defaultBrowserContext(self) -> 'BrowserContext':
        return self._defaultContext

    async def _disposeContext(self, contextId: str) -> None:
        await self._connection.send('Target.disposeBrowserContext', {'browserContextId': contextId,})
        self._contexts.pop(contextId, None)

    @staticmethod
    async def create(
        connection: Connection,
        contextIds: List[str],
        ignoreHTTPSErrors: bool,
        defaultViewport: Protocol.Page.Viewport,
        process: Optional[Popen] = None,
        closeCallback: Callable[[], Awaitable[None]] = None,
    ) -> 'Browser':
        """Create browser object."""
        browser = Browser(connection, contextIds, ignoreHTTPSErrors, defaultViewport, process, closeCallback)
        await connection.send('Target.setDiscoverTargets', {'discover': True})
        return browser

    async def _targetCreated(self, event: Dict) -> None:
        targetInfo = event['targetInfo']
        browserContextId = targetInfo.get('browserContextId')

        if browserContextId and browserContextId in self._contexts:
            context = self._contexts[browserContextId]
        else:
            context = self._defaultContext

        target = Target(
            targetInfo=targetInfo,
            browserContext=context,
            sessionFactory=lambda: self._connection.createSession(targetInfo),
            ignoreHTTPSErrors=self._ignoreHTTPSErrors,
            defaultViewport=self._defaultViewport,
            screenshotTaskQueue=self._screenshotTaskQueue,
            loop=self._connection.loop,
        )
        if targetInfo['targetId'] in self._targets:
            raise BrowserError('target should not exist before create.')
        self._targets[targetInfo['targetId']] = target
        if await target._initializedPromise:
            self.emit(Events.Browser.TargetCreated, target)
            context.emit(Events.BrowserContext.TargetCreated, target)

    async def _targetDestroyed(self, event: Dict) -> None:
        target = self._targets[event['targetId']]
        del self._targets[event['targetId']]
        target._closedCallback()
        if await target._initializedPromise:
            self.emit(Events.Browser.TargetDestroyed, target)
            target.browserContext.emit(Events.BrowserContext.TargetDestroyed, target)
        target._initializedCallback(False)

    async def _targetInfoChanged(self, event: Dict) -> None:
        target = self._targets.get(event['targetInfo']['targetId'])
        if not target:
            raise BrowserError('target should exist before targetInfoChanged')
        previousURL = target.url
        wasInitialized = target._isInitialized
        target._targetInfoChanged(event['targetInfo'])
        if wasInitialized and previousURL != target.url:
            self.emit(Events.Browser.TargetChanged, target)
            target.browserContext.emit(Events.BrowserContext.TargetChanged, target)

    @property
    def wsEndpoint(self) -> str:
        """Return websocket end point url."""
        return self._connection.url

    async def newPage(self) -> 'Page':
        """Make new page on this browser and return its object."""
        return await self._defaultContext.newPage()

    async def _createPageInContext(self, contextId: Optional[str]) -> 'Page':
        options = {'url': 'about:blank'}
        if contextId:
            options['browserContextId'] = contextId

        targetId = (await self._connection.send('Target.createTarget', options)).get('targetId')
        target = self._targets.get(targetId)
        if target is None or not await target._initializedPromise:
            raise BrowserError('Failed to create target for page.')
        page = await target.page()
        if page is None:
            raise BrowserError('Failed to create page.')
        return page

    def targets(self) -> List[Target]:
        """Get a list of all active targets inside the browser.

        In case of multiple browser contexts, this will return a list
        with all the targets in all browser contexts.
        """
        return [target for target in self._targets.values() if target._isInitialized]

    @property
    def target(self) -> Target:
        """get active browser target"""
        return next((target for target in self.targets() if target.type == 'browser'))

    async def waitForTarget(self, predicate: Callable[[Target], bool], timeout: float = 30_000) -> Target:
        """
        Wait for target that matches predicate function.
        :param predicate: function that takes 1 argument of Target object
        :param timeout: how long to wait for target in milliseconds,
        TimeoutError will be raised otherwise
        """
        if timeout:  # js uses ms while asyncio uses seconds
            timeout = timeout / 1_000
        existing_target = [target for target in self.targets() if predicate(target)]
        if existing_target:
            return existing_target[0]

        result_fut: Future[Target] = self.loop.create_future()

        def check(target: Target) -> None:
            if predicate(target):
                result_fut.set_result(target)

        self.on(Events.Browser.TargetCreated, check)
        self.on(Events.Browser.TargetChanged, check)
        result = await asyncio.wait_for(result_fut, timeout=timeout)
        self.remove_listener(Events.Browser.TargetCreated, check)
        self.remove_listener(Events.Browser.TargetChanged, check)
        return result

    @property
    async def pages(self) -> List['Page']:
        """Get all pages of this browser.

        Non visible pages, such as ``"background_page"``, will not be listed
        here. You can find then using :meth:`pyppeteer.target.Target.page`.

        In case of multiple browser contexts, this method will return a list
        with all the pages in all browser contexts.
        """
        pages = await asyncio.gather(*[context.pages() for context in self.browserContexts])
        return [p for ps in pages for p in ps]

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
        await self._closeCallback()
        await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect browser."""
        await self._connection.dispose()

    @property
    def isConnected(self) -> bool:
        return not self._connection._closed

    def _getVersion(self) -> Awaitable:
        return self._connection.send('Browser.getVersion')


class BrowserContext(AsyncIOEventEmitter):
    """BrowserContext provides multiple independent browser sessions.

    When a browser is launched, it has a single BrowserContext used by default.
    The method `browser.newPage()` creates a page in the default browser
    context.

    If a page opens another page, e.g. with a ``window.open`` call, the popup
    will belong to the parent page's browser context.

    Pyppeteer allows creation of "incognito" browser context with
    ``browser.createIncognitoBrowserContext()`` method.
    "incognito" browser contexts don't write any browser data to disk.

    .. code::

        # Create new incognito browser context
        context = await browser.createIncognitoBrowserContext()
        # Create a new page inside context
        page = await context.newPage()
        # ... do stuff with page ...
        await page.goto('https://example.com')
        # Dispose context once it's no longer needed
        await context.close()
    """

    def __init__(self, connection: Connection, browser: Browser, contextId: Optional[str]) -> None:
        super().__init__()
        self._connection = connection
        self._browser = browser
        self._id = contextId

    def targets(self) -> List[Target]:
        """Return a list of all active targets inside the browser context."""
        targets = []
        for target in self._browser.targets():
            if target.browserContext == self:
                targets.append(target)
        return targets

    async def pages(self) -> List['Page']:
        """Return list of all open pages.

        Non-visible pages, such as ``"background_page"``, will not be listed
        here. You can find them using :meth:`pyppeteer.target.Target.page`.
        """
        pages = [target.page() for target in self.targets() if target.type == 'page']
        return [page for page in await asyncio.gather(*pages) if page]

    def isIncognito(self) -> bool:
        """Return whether BrowserContext is incognito.

        The default browser context is the only non-incognito browser context.

        .. note::
            The default browser context cannot be closed.
        """
        return bool(self._id)

    async def overridePermissions(self, origin: str, permissions: Sequence[WebPermission]) -> None:
        web_perm_to_protocol = {
            'geolocation': 'geolocation',
            'midi': 'midi',
            'notifications': 'notifications',
            'push': 'push',
            'camera': 'videoCapture',
            'microphone': 'audioCapture',
            'background-sync': 'backgroundSync',
            'ambient-light-sensor': 'sensors',
            'accelerometer': 'sensors',
            'gyroscope': 'sensors',
            'magnetometer': 'sensors',
            'accessibility-events': 'accessibilityEvents',
            'clipboard-read': 'clipboardRead',
            'clipboard-write': 'clipboardWrite',
            'payment-handler': 'paymentHandler',
            # chrome specific
            'midi-sysex': 'midiSysex',
        }
        protocol_perms = []
        for perm in permissions:
            protocol_perm = web_perm_to_protocol.get(perm)
            if protocol_perm is None:
                raise RuntimeError(f'Unknown permission: {perm}')
            protocol_perms.append(perm)
        await self._connection.send(
            'Browser.grantPermissions', {'origin': origin, 'browserContextId': self._id, 'permissions': permissions}
        )

    async def clearPermissionOverrides(self) -> None:
        await self._connection.send('Browser.resetPermissions', {'browserContextId': self._id})

    async def newPage(self) -> 'Page':
        """Create a new page in the browser context."""
        return await self._browser._createPageInContext(self._id)

    @property
    def browser(self) -> Browser:
        """Return the browser this browser context belongs to."""
        return self._browser

    async def close(self) -> None:
        """Close the browser context.

        All the targets that belongs to the browser context will be closed.

        .. note::
            Only incognito browser context can be closed.
        """
        if self._id is None:
            raise BrowserError('Non-incognito profile cannot be closed')
        await self._browser._disposeContext(self._id)
