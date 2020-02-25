#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle watcher module

puppeteer equivalent: lib/LifecycleWatcher.js
"""
import asyncio
from functools import partial
from typing import Union, List

from pyppeteer import helper
from pyppeteer.errors import BrowserError, TimeoutError
from pyppeteer.events import Events
from pyppeteer.frame_manager import FrameManager, Frame

puppeteerToProtocolLifecycle = {
    'load': 'load',
    'domcontentloaded': 'DOMContentLoaded',
    'networkidle0': 'networkIdle',
    'networkidle2': 'networkAlmostIdle',
}


class LifecycleWatcher:

    def __init__(self, frameManager: FrameManager, frame: Frame, waitUntil: Union[str, List[str]], timeout: int,):
        if isinstance(waitUntil, str):
            waitUntil = [waitUntil]

        self._expectedLifecycle = []
        for wait_for in waitUntil:
            protocol_event = puppeteerToProtocolLifecycle.get(wait_for)
            if not protocol_event:
                raise BrowserError(f'Unknown value '
                                   f'for options.waitUntil: {waitUntil}')
            self._expectedLifecycle.append(protocol_event)

        self._frameManager = frameManager
        self._frame = frame
        self._initialLoaderId = frame._loaderId
        self._timeout = timeout

        self._navigationRequest: 'Request' = None
        self._eventListeners = [
            helper.addEventListener(
                frameManager._client,
                Events.CDPSession.Disconnected,
                partial(
                    self._terminate,
                    BrowserError('Navigation failed because browser has disconnected'))
            ),
            helper.addEventListener(
                self._frameManager,
                Events.FrameManager.LifecycleEvent,
                self._checkLifecycleComplete,
            ),
            helper.addEventListener(
                self._frameManager,
                Events.FrameManager.FrameNavigatedWithinDocument,
                self._navigatedWithinDocument
            ),
            helper.addEventListener(
                self._frameManager,
                Events.FrameManager.FrameDetached,
                self._onFrameDetached
            ),
            helper.addEventListener(
                self._frameManager.networkManager,
                Events.NetworkManager.Request,
                self._onRequest
            )
        ]

        # self._bodyLoadedPromise = self._client._loop.create_future()
        # use create_future instead of Future
        create_future = self._frameManager._client._loop.create_future

        self._sameDocumentNavigationPromise = create_future()
        self._lifecyclePromise = create_future()
        self._newDocumentNavigationPromise = create_future()
        self._timeoutPromise = self._createTimeoutPromise()
        self._terminationPromise = create_future()
        self._checkLifecycleComplete()

    def _onRequest(self, request: 'Request'):
        if request.frame != self._frame or not request.isNavigationRequest():
            return
        self._navigationRequest = request

    def _onFrameDetached(self, frame):
        if self._frame == frame:
            self._terminationCallback(BrowserError('Navigating frame was detached'))
            return
        self._checkLifecycleComplete()

    @property
    def navigationResponse(self):
        if self._navigationRequest.response():
            return self._navigationRequest

    def _terminate(self, error):
        self._terminationCallback(error)

    @property
    def sameDocumentNavigationPromise(self):
        return self._sameDocumentNavigationPromise

    @property
    def newDocumentNavigationPromise(self):
        return self._newDocumentNavigationPromise

    @property
    def lifecyclePromise(self):
        return self._lifecyclePromise

    def timeoutOrTerminationPromise(self):
        asyncio.wait([self._timeoutPromise, self._terminationPromise],
                     loop=self._frameManager._client._loop,
                     return_when='FIRST_COMPLETED')

    def _createTimeoutPromise(self):
        future = self._frameManager._client._loop.create_future()
        if not self._timeout:
            return future
        errorMessage = 'Navigation timeout of {} ms exceeded'.format(self._timeout)
        self._maxTimeout = self._frameManager._client._loop.create_task(self._raiseTimeoutError(errorMessage))

    async def _raiseTimeoutError(self, message: str):
        await asyncio.sleep(self._timeout)
        raise TimeoutError(message)

    def _navigatedWithinDocument(self, frame):
        if frame != self._frame:
            return
        self._hasSameDocumentNavigation = True
        self._checkLifecycleComplete()

    def _checkLifecycleComplete(self):
        def check_lifecycle(frame: 'Frame', expected_lifecycle: List[str]):
            for event in expected_lifecycle:
                if event in frame._lifecycleEvents:
                    return False
            for child in frame.childFrames:
                if not check_lifecycle(child, expected_lifecycle):
                    return False
            return True

        if not check_lifecycle(self._frame, self._expectedLifecycle):
            return
        self._lifecycleCallback()

        if self._frame._loaderId == self._initialLoaderId \
                and not self._hasSameDocumentNavigation:
            return
        if self._frame._loaderId != self._initialLoaderId:
            self._newDocumentNavigationCompleteCallback()

    def dispose(self):
        helper.removeEventListeners(self._eventListeners)
        self._maxTimeout.cancel()

    def _sameDocumentNavigationCompleteCallback(self, value=None) -> None:
        self._sameDocumentNavigationPromise.set_value(value)

    def _lifecycleCallback(self, value=None) -> None:
        self._lifecyclePromise.set_value(value)

    def _newDocumentNavigationCompleteCallback(self, value=None) -> None:
        self._lifecyclePromise.set_value(value)

    def _terminationCallback(self, value=None) -> None:
        self._lifecyclePromise.set_value(value)
