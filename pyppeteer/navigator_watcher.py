#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Navigator Watcher module."""

import asyncio
import concurrent.futures

from typing import Any, Awaitable, Optional, TYPE_CHECKING, Union

from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.errors import NetworkError

if TYPE_CHECKING:
    from typing import Callable, List, Set  # noqa: F401


class NavigatorWatcher:
    """NavigatorWatcher class."""

    def __init__(self, client: Session, ignoreHTTPSErrors: Any,
                 options: dict = None, **kwargs: Any) -> None:
        """Make new navigator watcher."""
        if options is None:
            options = {}
        options.update(kwargs)
        self._client = client
        self._ignoreHTTPSErrors = ignoreHTTPSErrors
        self._timeout = options.get('timeout', 3000)
        self._idleTime = options.get('networkIdleTimeout', 1000)
        self._idleTimer: Optional[Union[asyncio.Future, asyncio.Handle]] = None
        self._idleInflight = options.get('networkIdleInflight', 2)
        self._waitUntil = options.get('waitUntil', 'load')
        if self._waitUntil not in ('load', 'networkidle'):
            raise ValueError(
                f'Unknown value for options.waitUntil: {self._waitUntil}')

    def _raise_error(self, error: Exception = Exception()) -> None:
        raise error

    async def waitForNavigation(self) -> None:
        """Wait until navigatoin completes."""
        self._requestIds: Set[str] = set()
        self._eventListeners: List[dict] = list()
        navigationPromises = list()
        loop = asyncio.get_event_loop()

        def watchdog_cb(fut: Awaitable) -> None:
            self._raise_error(asyncio.TimeoutError(
                'Navigation Timeout Exceeded: {} ms exceeded'.format(
                    self._timeout)
            ))

        watchdog: asyncio.Future = asyncio.ensure_future(
            asyncio.sleep(self._timeout / 1000))
        self._maximumTimer = watchdog
        watchdog.add_done_callback(watchdog_cb)
        navigationPromises.append(watchdog)

        if not self._ignoreHTTPSErrors:
            certificateError = loop.create_future()
            self._eventListeners.append(
                helper.addEventListener(
                    self._client, 'Security.certificateError',
                    lambda event: certificateError.set_exception(
                        NetworkError('SSL Certificate error: ' +
                                     str(event.get('errorType')))
                    )
                )
            )
            navigationPromises.append(certificateError)

        if self._waitUntil == 'load':
            loadEventFired = loop.create_future()
            self._eventListeners.append(
                helper.addEventListener(
                    self._client, 'Page.loadEventFired',
                    lambda event: loadEventFired.set_result(None)
                )
            )
            navigationPromises.append(loadEventFired)
        else:
            self._eventListeners.extend((
                helper.addEventListener(self._client, 'Network.requestWillBeSent', self._onLoadingStarted),  # noqa
                helper.addEventListener(self._client, 'Network.loadingFinished', self._onLoadingCompleted),  # noqa
                helper.addEventListener(self._client, 'Network.loadingFailed', self._onLoadingCompleted),  # noqa
                helper.addEventListener(self._client, 'Network.webSocketCreated', self._onLoadingStarted),  # noqa
                helper.addEventListener(self._client, 'Network.webSocketClosed', self._onLoadingCompleted),  # noqa
            ))
            networkIdle = loop.create_future()
            self._networkIdleCallback = lambda f: networkIdle.set_result(None)
            navigationPromises.append(networkIdle)

        await asyncio.wait(navigationPromises,
                           return_when=concurrent.futures.FIRST_COMPLETED)
        if not watchdog.done():
            watchdog.remove_done_callback(watchdog_cb)
        self._cleanup()

    def cancel(self) -> None:
        """Cancel navigation."""
        self._cleanup()

    def _onLoadingStarted(self, event: dict) -> None:
        self._requestIds.add(event.get('requestIds', ''))
        if len(self._requestIds) > self._idleInflight:
            clearTimeout(self._idleTimer)
            self._idleTimer = None

    def _onLoadingCompleted(self, event: dict) -> None:
        self._requestIds.remove(event.get('requestIds', ''))
        if len(self._requestIds) <= self._idleInflight and not self._idleTimer:
            self._idleTimer = asyncio.get_event_loop().call_later(
                self._idleTime / 1000,
                self._networkIdleCallback,
            )

    def _cleanup(self, ) -> None:
        helper.removeEventListeners(self._eventListeners)
        clearTimeout(self._idleTimer)
        clearTimeout(self._maximumTimer)


def clearTimeout(fut: Optional[Union[asyncio.Future, asyncio.Handle]]) -> None:
    """Cancel timer task."""
    if fut:
        fut.cancel()
