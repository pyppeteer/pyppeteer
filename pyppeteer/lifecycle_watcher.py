#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle Watcher module

puppeteer equivalent: lib/LifecycleWatcher.js
"""

import asyncio
from functools import partial
from typing import Awaitable, List, Union, Optional, TYPE_CHECKING

from pyppeteer import helpers
from pyppeteer.errors import TimeoutError, BrowserError, PageError
from pyppeteer.events import Events
from pyppeteer.helpers import safe_future_set_result
from pyppeteer.models import WaitTargets
from pyppeteer.network_manager import Request, Response

if TYPE_CHECKING:
    from pyppeteer.frame import Frame, FrameManager

pyppeteerToProtocolLifecycle = {
    'load': 'load',
    'domcontentloaded': 'DOMContentLoaded',
    'documentloaded': 'DOMContentLoaded',
    'networkidle0': 'networkIdle',
    'networkidle2': 'networkAlmostIdle',
}


class LifecycleWatcher:
    """LifecycleWatcher class."""

    def __init__(
        self, frameManager: 'FrameManager', frame: 'Frame', timeout: Optional[float], waitUntil: WaitTargets = 'load',
    ) -> None:
        """Make new LifecycleWatcher"""
        self._expectedLifecycle: List[str] = []
        if isinstance(waitUntil, str):
            waitUntil = [waitUntil]
        for value in waitUntil:
            try:
                protocolEvent = pyppeteerToProtocolLifecycle[value]
            except AttributeError:
                raise ValueError(f'Unknown value for options.waitUntil: {value}')
            else:
                self._expectedLifecycle.append(protocolEvent)

        self._futures = []
        self._frameManager = frameManager
        self._frame = frame
        self._initialLoaderId = frame._loaderId
        self._timeout = timeout
        self._navigationRequest: Optional[Request] = None
        self._hasSameDocumentNavigation = False
        self._eventListeners = [
            helpers.addEventListener(
                self._frameManager._client,
                Events.CDPSession.Disconnected,
                partial(self._terminate, BrowserError('Navigation failed because browser has disconnected')),
            ),
            helpers.addEventListener(
                self._frameManager, Events.FrameManager.LifecycleEvent, self._checkLifecycleComplete,
            ),
            helpers.addEventListener(
                self._frameManager, Events.FrameManager.FrameNavigatedWithinDocument, self._navigatedWithinDocument,
            ),
            helpers.addEventListener(self._frameManager, Events.FrameManager.FrameDetached, self._onFrameDetached,),
            helpers.addEventListener(
                self._frameManager.networkManager, Events.NetworkManager.Request, self._onRequest,
            ),
        ]
        self.loop = self._frameManager._client.loop

        self._lifecycleFuture = self.loop.create_future()
        self._sameDocumentNavigationFuture = self.loop.create_future()
        self._newDocumentNavigationFuture = self.loop.create_future()
        self._terminationFuture = self.loop.create_future()

        self._timeoutFuture = self._createTimeoutPromise()

        for class_attr in dir(self):
            if class_attr.endswith('Future'):
                self._futures.append(self.__getattribute__(class_attr))

        self._checkLifecycleComplete()

    @property
    def lifecycleFuture(self) -> Awaitable[None]:
        return self._lifecycleFuture

    @property
    def sameDocumentNavigationFuture(self) -> Awaitable[None]:
        return self._sameDocumentNavigationFuture

    @property
    def newDocumentNavigationFuture(self) -> Awaitable[None]:
        return self._newDocumentNavigationFuture

    def _onRequest(self, request: Request) -> None:
        if request.frame == self._frame and request.isNavigationRequest:
            self._navigationRequest = request

    def _onFrameDetached(self, frame: 'Frame' = None) -> None:
        # note: frame never appears to specified, left in for compatibility
        if frame == self._frame:
            self._terminationFuture.set_exception(PageError('Navigating frame was detached'))
        else:
            self._checkLifecycleComplete()

    def _terminate(self, error: Exception) -> None:
        self._terminationFuture.set_result(error)

    def navigationResponse(self) -> Optional[Response]:
        return self._navigationRequest.response if self._navigationRequest else None

    @property
    def timeoutOrTerminationFuture(self) -> Awaitable:
        return self._frame._client.loop.create_task(helpers.future_race(self._timeoutFuture, self._terminationFuture))

    def _createTimeoutPromise(self) -> Awaitable[None]:
        self._maximumTimerFuture = self.loop.create_future()
        if self._timeout:
            errorMessage = f'Navigation Timeout Exceeded: {self._timeout}ms exceeded.'  # noqa: E501

            async def _timeout_func() -> None:
                await asyncio.sleep(self._timeout / 1000)
                self._maximumTimerFuture.set_exception(TimeoutError(errorMessage))

            self._timeoutTimerFuture: Union[asyncio.Task, asyncio.Future] = self.loop.create_task(_timeout_func())
        else:
            self._timeoutTimerFuture = self.loop.create_future()
        return self._maximumTimerFuture

    def _navigatedWithinDocument(self, frame: 'Frame' = None) -> None:
        # note: frame never appears to specified, left in for compatibility
        if frame == self._frame:
            self._hasSameDocumentNavigation = True
            self._checkLifecycleComplete()

    def _checkLifecycleComplete(self, _=None) -> None:
        if not self._checkLifecycle(self._frame, self._expectedLifecycle):
            return
        # python can set future only once but this might be called multiple times
        safe_future_set_result(self._lifecycleFuture, None)
        if self._frame._loaderId == self._initialLoaderId and not self._hasSameDocumentNavigation:
            return
        if self._hasSameDocumentNavigation:
            safe_future_set_result(self._sameDocumentNavigationFuture, None)
        if self._frame._loaderId != self._initialLoaderId:
            safe_future_set_result(self._newDocumentNavigationFuture, None)

    def _checkLifecycle(self, frame: 'Frame', expectedLifecycle: List[str]) -> bool:
        for event in expectedLifecycle:
            if event not in frame._lifecycleEvents:
                return False
        for child in frame.childFrames:
            if not self._checkLifecycle(child, expectedLifecycle):
                return False
        return True

    def dispose(self) -> None:
        helpers.removeEventListeners(self._eventListeners)
        for fut in self._futures:
            try:
                fut.cancel()
            except AttributeError:
                continue
