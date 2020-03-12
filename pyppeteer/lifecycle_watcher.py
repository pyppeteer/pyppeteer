#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle Watcher module

puppeteer equivalent: lib/LifecycleWatcher.js
"""

import asyncio
from asyncio import FIRST_COMPLETED, Future
from functools import partial
from typing import Awaitable, Dict, List, Union, Optional, TYPE_CHECKING, Literal

from pyppeteer import helper
from pyppeteer.errors import TimeoutError, BrowserError, PageError, DeprecationError
from pyppeteer.events import Events
from pyppeteer.network_manager import Request

if TYPE_CHECKING:
    from pyppeteer.frame_manager import FrameManager, Frame

pyppeteerToProtocolLifecycle = {
    'load': 'load',
    'domcontentloaded': 'DOMContentLoaded',
    'documentloaded': 'DOMContentLoaded',
    'networkidle0': 'networkIdle',
    'networkidle2': 'networkAlmostIdle',
}

WaitTargets = Literal['load', 'domcontentloaded', 'networkidle0', 'networkidle2']


class LifecycleWatcher:
    """LifecycleWatcher class."""

    def __init__(
        self,
        frameManager: 'FrameManager',
        frame: 'Frame',
        timeout: int,
        waitUntil: Union[WaitTargets, List[WaitTargets]] = 'load',
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
        self._navigationRequest: Request = None
        self._hasSameDocumentNavigation = False
        self._eventListeners = [
            helper.addEventListener(
                self._frameManager._client,
                Events.CDPSession.Disconnected,
                partial(self._terminate, BrowserError('Navigation failed because browser has disconnected')),
            ),
            helper.addEventListener(
                self._frameManager, Events.FrameManager.LifecycleEvent, self._checkLifecycleComplete,
            ),
            helper.addEventListener(
                self._frameManager, Events.FrameManager.FrameNavigatedWithinDocument, self._navigatedWithinDocument,
            ),
            helper.addEventListener(self._frameManager, Events.FrameManager.FrameDetached, self._onFrameDetached,),
            helper.addEventListener(self._frameManager.networkManager, Events.NetworkManager.Request, self._onRequest,),
        ]
        self._loop = self._frameManager._client._loop

        self._lifecycleFuture = self._loop.create_future()
        self._sameDocumentNavigationFuture = self._loop.create_future()
        self._newDocumentNavigationFuture = self._loop.create_future()
        self._terminationFuture = self._loop.create_future()

        self._timeoutFuture = self._createTimeoutPromise()

        for class_attr in dir(self):
            if class_attr.endswith('Future') and isinstance(self.__getattribute__(class_attr), Future):
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
        if request.frame == self._frame and request.isNavigationRequest():
            self._navigationRequest = request

    def _onFrameDetached(self, frame: 'Frame' = None) -> None:
        # note: frame never appears to specified, left in for compatibility
        if frame == self._frame:
            self._terminationFuture.set_exception(PageError('Navigating frame was detached'))
        else:
            self._checkLifecycleComplete()

    def _terminate(self, error: Exception) -> None:
        self._terminationFuture.set_result(error)

    def navigationResponse(self) -> Optional[Request]:
        return self._navigationRequest.response if self._navigationRequest else None

    @property
    def timeoutOrTerminationFuture(self) -> Awaitable:
        return helper.future_race(self._timeoutFuture, self._terminationFuture)

    def _createTimeoutPromise(self) -> Awaitable[None]:
        self._maximumTimerFuture = self._loop.create_future()
        if self._timeout:
            errorMessage = f'Navigation Timeout Exceeded: {self._timeout}ms exceeded.'  # noqa: E501

            async def _timeout_func() -> None:
                await asyncio.sleep(self._timeout / 1000)
                self._maximumTimerFuture.set_exception(TimeoutError(errorMessage))

            self._timeoutTimerFuture: Union[asyncio.Task, asyncio.Future] = self._loop.create_task(
                _timeout_func()
            )  # noqa: E501
        else:
            self._timeoutTimerFuture = self._loop.create_future()
        return self._maximumTimerFuture

    def _navigatedWithinDocument(self, frame: 'Frame' = None) -> None:
        # note: frame never appears to specified, left in for compatibility
        if frame == self._frame:
            self._hasSameDocumentNavigation = True
            self._checkLifecycleComplete()

    def _checkLifecycleComplete(self, _=None) -> None:
        if not self._checkLifecycle(self._frame, self._expectedLifecycle):
            return
        self._lifecycleFuture.set_result(None)
        if self._frame._loaderId == self._initialLoaderId and not self._hasSameDocumentNavigation:
            return
        if self._hasSameDocumentNavigation:
            self._sameDocumentNavigationFuture.set_result(None)
        if self._frame._loaderId != self._initialLoaderId:
            self._newDocumentNavigationFuture.set_result(None)

    def _checkLifecycle(self, frame: 'Frame', expectedLifecycle: List[str]) -> bool:
        for event in expectedLifecycle:
            if event not in frame._lifecycleEvents:
                return False
        for child in frame.childFrames:
            if not self._checkLifecycle(child, expectedLifecycle):
                return False
        return True

    def dispose(self) -> None:
        helper.removeEventListeners(self._eventListeners)
        for fut in self._futures:
            # todo: remove try except (probably not needed)
            try:
                fut.cancel()
            except AttributeError:
                continue
