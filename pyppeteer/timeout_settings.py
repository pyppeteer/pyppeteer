#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Timeout setting module

puppeteer equivelent: TimeoutSettings.js
"""

DEFAULT_TIMEOUT = 30_000  # 30 seconds


class TimeoutSettings(object):
    def __init__(self):
        self._defaultTimeout = None
        self._defaultNavigationTimeout = None

    def setDefaultTimeout(self, timeout):
        self._defaultTimeout = timeout

    def setDefaultNavigationTimeout(self, timeout):
        self._defaultNavigationTimeout = timeout

    @property
    def navigationTimeout(self):
        if self._defaultNavigationTimeout:
            return self._defaultNavigationTimeout
        if self._defaultTimeout:
            return self._defaultTimeout
        return DEFAULT_TIMEOUT

    @property
    def timeout(self):
        if self._defaultTimeout:
            return self._defaultTimeout
        return DEFAULT_TIMEOUT
