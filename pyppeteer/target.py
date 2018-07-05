#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Target module."""

import asyncio
from typing import Dict, Optional, TYPE_CHECKING

from pyppeteer.connection import CDPSession
from pyppeteer.page import Page

if TYPE_CHECKING:
    from pyppeteer.browser import Browser  # noqa: F401


class Target(object):
    """Browser's target class."""

    def __init__(self, browser: 'Browser', targetInfo: Dict) -> None:
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
        """Get type of this target.

        Type can be ``'page'``, ``'service_worker'``, ``'browser'``, or
        ``'other'``.
        """
        _type = self._targetInfo['type']
        if _type in ['page', 'service_worker', 'browser']:
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
            from pyppeteer.browser import Browser  # noqa: F811
            self._browser.emit(Browser.Events.TargetChanged, self)
