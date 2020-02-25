#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Task Queue module

puppeteer equivalent: lib/TaskQueue.js
"""
import asyncio
from typing import Awaitable


class TaskQueue:
    def __init__(self):
        self._last_future = asyncio.Future()
        self._last_future.set_result(None)

    async def postTask(self, task: Awaitable):
        result = await self._last_future
        self._last_future = task
        return result
