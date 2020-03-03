#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Emulation Manager module."""
import asyncio

from pyppeteer.connection import CDPSession


class EmulationManager:
    """EmulationManager class."""

    def __init__(self, client: CDPSession) -> None:
        """Make new emulation manager."""
        self._client = client
        self._emulatingMobile = False
        self._hasTouch = False
        self._emulatingMobile = False

    async def emulateViewport(self, viewport: dict) -> bool:
        """
        Evaluate viewport.
        :param viewport: dictionary which supports keys: isMobile, width, height,
            deviceScaleFactor, isLandscape, hasTouch
        """
        mobile = viewport.get('isMobile', False)
        width = viewport.get('width')
        height = viewport.get('height')
        deviceScaleFactor = viewport.get('deviceScaleFactor', 1)
        if viewport.get('isLandscape'):
            screenOrientation = {'angle': 90, 'type': 'landscapePrimary'}
        else:
            screenOrientation = {'angle': 0, 'type': 'portraitPrimary'}
        hasTouch = viewport.get('hasTouch', False)

        await asyncio.gather(
            self._client.send(
                'Emulation.setDeviceMetricsOverride', {
                    'mobile': mobile,
                    'width': width,
                    'height': height,
                    'deviceScaleFactor': deviceScaleFactor,
                    'screenOrientation': screenOrientation,
                }),
            self._client.send(
                'Emulation.setTouchEmulationEnabled', {'enabled': hasTouch}
            )
        )
        reloadNeeded = self._emulatingMobile != mobile or self._hasTouch != hasTouch
        self._emulatingMobile = mobile
        self._hasTouch = hasTouch
        return reloadNeeded
