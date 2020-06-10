#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Timeout setting module

puppeteer equivalent: TimeoutSettings.js
"""

DEFAULT_TIMEOUT = 30_000  # 30 seconds


class TimeoutSettings:
    def __init__(self):
        self._defaultTimeout = None
        self._defaultNavigationTimeout = None

    def setDefaultTimeout(self, timeout: float) -> None:
        self._defaultTimeout = timeout

    def setDefaultNavigationTimeout(self, timeout: float) -> None:
        self._defaultNavigationTimeout = timeout

    @property
    def navigationTimeout(self) -> float:
        if self._defaultNavigationTimeout:
            return self._defaultNavigationTimeout
        if self._defaultTimeout:
            return self._defaultTimeout
        return DEFAULT_TIMEOUT

    @property
    def timeout(self) -> float:
        if self._defaultTimeout:
            return self._defaultTimeout
        return DEFAULT_TIMEOUT
