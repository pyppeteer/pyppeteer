#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle Watcher module

puppeteer equivalent: lib/LifecycleWatcher.js
"""

import asyncio
from asyncio import Future, FIRST_COMPLETED
from functools import partial
from typing import Any, Awaitable, Dict, List, Union

from pyppeteer import helper
from pyppeteer.errors import TimeoutError, BrowserError, PageError
from pyppeteer.events import Events
from pyppeteer.frame_manager import FrameManager, Frame
from pyppeteer.network_manager import Request
from pyppeteer.util import merge_dict

pyppeteerToProtocolLifecycle = {
    'load': 'load',
    'domcontentloaded': 'DOMContentLoaded',
    'documentloaded': 'DOMContentLoaded',
    'networkidle0': 'networkIdle',
    'networkidle2': 'networkAlmostIdle',
}


class LifecycleWatcher:
    """LifecycleWatcher class."""

    def __init__(self, frameManager: FrameManager, frame: Frame, timeout: int,
                 options: Dict = None, **kwargs: Any) -> None:
        """Make new LifecycleWatcher"""
        options = merge_dict(options, kwargs)
        self._validate_options_and_set_expected_lifecycle(options)
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
                partial(
                    self._terminate,
                    BrowserError('Navigation failed because browser has disconnected'))
            ),
            helper.addEventListener(
                self._frameManager,
                FrameManager.Events.LifecycleEvent,
                self._checkLifecycleComplete,
            ),
            helper.addEventListener(
                self._frameManager,
                FrameManager.Events.FrameNavigatedWithinDocument,
                self._navigatedWithinDocument,
            ),
            helper.addEventListener(
                self._frameManager,
                FrameManager.Events.FrameDetached,
                self._onFrameDetached,
            ),
            helper.addEventListener(
                self._frameManager.networkManager(),
                Events.NetworkManager.Request,
                self._onRequest,
            )
        ]
        self._loop = self._frameManager._client._loop

        self._lifecycleCompleteFuture = self._loop.create_future()
        self._sameDocumentNavigationFuture = self._loop.create_future()
        self._newDocumentNavigationFuture = self._loop.create_future()
        self._terminationFuture = self._loop.create_future()

        self._timeoutPromise = self._createTimeoutPromise()
        self._checkLifecycleComplete()

    @property
    def lifecycleComplete(self):
        return self._lifecycleCompleteFuture

    @property
    def sameDocumentNavigationComplete(self):
        return self._sameDocumentNavigationFuture

    @property
    def newDocumentNavigationComplete(self):
        return self._newDocumentNavigationFuture


    def _validate_options_and_set_expected_lifecycle(self, options: Dict) -> None:  # noqa: C901
        if 'networkIdleTimeout' in options:
            raise ValueError(
                '`networkIdleTimeout` option is no longer supported.')
        if 'networkIdleInflight' in options:
            raise ValueError(
                '`networkIdleInflight` option is no longer supported.')
        if options.get('waitUntil') == 'networkidle':
            raise ValueError(
                '`networkidle` option is no longer supported. '
                'Use `networkidle2` instead.')
        if options.get('waitUntil') == 'documentloaded':
            import logging
            logging.getLogger(__name__).warning(
                '`documentloaded` option is no longer supported. '
                'Use `domcontentloaded` instead.')
        _waitUntil = options.get('waitUntil', 'load')
        if isinstance(_waitUntil, list):
            waitUntil = _waitUntil
        elif isinstance(_waitUntil, str):
            waitUntil = [_waitUntil]
        else:
            raise TypeError(
                '`waitUntil` option should be str or List of str, '
                f'but got type {type(_waitUntil)}'
            )
        self._expectedLifecycle: List[str] = []
        for value in waitUntil:
            try:
                protocolEvent = pyppeteerToProtocolLifecycle[value]
            except AttributeError:
                raise ValueError(f'Unknown value for options.waitUntil: {value}')
            else:
                self._expectedLifecycle.append(protocolEvent)

    def _onRequest(self, request: 'Request'):
        if request.frame != self._frame or not request.isNavigationRequest():
            return
        self._navigationRequest = request

    def _onFrameDetached(self, frame: Frame):
        if frame == self._frame:
            self._terminationFuture.set_exception(PageError('Navigating frame was detached'))
            return
        self._checkLifecycleComplete()

    def timeoutOrTerminationPromise(self):
        return asyncio.wait([self._timeoutPromise, self._terminationFuture], return_when=FIRST_COMPLETED)

    def _createTimeoutPromise(self) -> Awaitable[None]:
        self._maximumTimer = self._loop.create_future()
        if self._timeout:
            errorMessage = f'Navigation Timeout Exceeded: {self._timeout}ms exceeded.'  # noqa: E501

            async def _timeout_func() -> None:
                await asyncio.sleep(self._timeout / 1000)
                self._maximumTimer.set_exception(TimeoutError(errorMessage))

            self._timeout_timer: Union[asyncio.Task, asyncio.Future] = self._loop.create_task(
                _timeout_func())  # noqa: E501
        else:
            self._timeout_timer = self._loop.create_future()
        return self._maximumTimer

    def navigationResponse(self) -> Any:
        return self._navigationRequest.response() if self._navigationRequest else None

    def _terminate(self):
        self._terminato

    def _navigatedWithinDocument(self, frame: Frame = None) -> None:
        if frame != self._frame:
            return
        self._hasSameDocumentNavigation = True
        self._checkLifecycleComplete()

    def _checkLifecycleComplete(self) -> None:
        if not self._checkLifecycle(self._frame, self._expectedLifecycle):
            return
        self._lifecycleCompleteFuture.set_result(None)
        if self._frame._loaderId == self._initialLoaderId and not self._hasSameDocumentNavigation:
            return
        if self._hasSameDocumentNavigation:
            self._sameDocumentNavigationFuture.set_result(None)
        if self._frame._loaderId != self._initialLoaderId:
            self._newDocumentNavigationFuture.set_result(None)

    def _checkLifecycle(self, frame: Frame, expectedLifecycle: List[str]) -> bool:
        for event in expectedLifecycle:
            if event not in frame._lifecycleEvents:
                return False
        for child in frame.childFrames:
            if not self._checkLifecycle(child, expectedLifecycle):
                return False
        return True

    def cancel(self) -> None:
        """Cancel navigation."""
        self._cleanup()

    def dispose(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        helper.removeEventListeners(self._eventListeners)
        # self._lifecycleCompletePromise.cancel()
        self._maximumTimer.cancel()
        self._timeout_timer.cancel()
