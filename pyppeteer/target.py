#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Target module."""

import asyncio
from typing import Callable, Dict, Optional, Awaitable, TYPE_CHECKING

from pyppeteer.connection import CDPSession
from pyppeteer.events import Events
from pyppeteer.helpers import safe_future_set_result
from pyppeteer.models import Viewport
from pyppeteer.page import Page
from pyppeteer.task_queue import TaskQueue
from pyppeteer.worker import Worker

if TYPE_CHECKING:
    from pyppeteer.browser import Browser, BrowserContext


class Target:
    """Browser's target class."""

    def __init__(
        self,
        targetInfo: Dict,
        browserContext: 'BrowserContext',
        sessionFactory: Callable[[], Awaitable[CDPSession]],
        ignoreHTTPSErrors: bool,
        defaultViewport: Viewport,
        screenshotTaskQueue: TaskQueue,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._targetInfo = targetInfo
        self._browserContext = browserContext
        self._targetId = targetInfo.get('targetId', '')
        self._sessionFactory = sessionFactory
        self._ignoreHTTPSErrors = ignoreHTTPSErrors
        self._defaultViewport = defaultViewport
        self._screenshotTaskQueue = screenshotTaskQueue
        self._page: Optional[Page] = None
        self._workerFuture: Optional[Awaitable[Worker]] = None
        self.loop = loop

        self._initializedPromise = self.loop.create_future()
        self._isClosedPromise = self.loop.create_future()
        self._isInitialized = self._targetInfo['type'] != 'page' or self._targetInfo['url'] != ''
        if self._isInitialized:
            self._initializedCallback(True)

    def _initializedCallback(self, success: bool) -> None:
        if not success:
            return safe_future_set_result(self._initializedPromise, False)
        opener = self.opener
        if not opener or not opener._page or self.type != 'page':
            return self._initializedPromise.set_result(True)
        openerPage = opener._page
        if not openerPage.listeners(Events.Page.Popup):
            return self._initializedPromise.set_result(True)
        openerPage.emit(Events.Page.Popup, openerPage)
        return self._initializedPromise.set_result(True)

    def _closedCallback(self) -> None:
        self._isClosedPromise.set_result(None)

    async def createCDPSession(self) -> CDPSession:
        """Create a Chrome Devtools Protocol session attached to the target."""
        return await self._sessionFactory()

    async def page(self) -> Optional[Page]:
        """Get page of this target.

        If the target is not of type "page" or "background_page", return
        ``None``.
        """
        if self._page:
            return self._page
        if self._targetInfo['type'] in ['page', 'background_page']:
            session = await self._sessionFactory()
            self._page = await Page.create(
                client=session,
                target=self,
                ignoreHTTPSErrors=self._ignoreHTTPSErrors,
                defaultViewport=self._defaultViewport,
                screenshotTaskQueue=self._screenshotTaskQueue,
            )
        return self._page

    def worker(self) -> Optional[Awaitable[Worker]]:
        _type = self._targetInfo['type']
        if _type not in ['service_worker', 'shared_worker']:
            return None
        if not self._workerFuture:

            async def worker_fut_task() -> Worker:
                nonlocal self
                session = await self._sessionFactory()
                return Worker(session, self._targetInfo['url'], lambda *_: None, lambda *_: None)

            self._workerFuture = self.loop.create_task(worker_fut_task())
            return self._workerFuture

    @property
    def url(self) -> str:
        """Get url of this target."""
        return self._targetInfo['url']

    @property
    def type(self) -> str:
        """Get type of this target.

        Type can be ``'page'``, ``'background_page'``, ``'service_worker'``,
        ``'browser'``, or ``'other'``.
        """
        _type = self._targetInfo['type']
        if _type in ['page', 'background_page', 'service_worker', 'shared_worker', 'browser']:
            return _type
        return 'other'

    @property
    def browser(self) -> 'Browser':
        """Get the browser the target belongs to."""
        return self._browserContext.browser

    @property
    def browserContext(self) -> 'BrowserContext':
        """Return the browser context the target belongs to."""
        return self._browserContext

    @property
    def opener(self) -> Optional['Target']:
        """Get the target that opened this target.

        Top-level targets return ``None``.
        """
        openerId = self._targetInfo.get('openerId')
        if openerId is None:
            return None
        return self.browser._targets.get(openerId)

    def _targetInfoChanged(self, targetInfo: Dict) -> None:
        self._targetInfo = targetInfo

        if not self._isInitialized and (self._targetInfo['type'] != 'page' or self._targetInfo['url'] != ''):
            self._isInitialized = True
            self._initializedCallback(True)
            return
