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
        self._chain = None

    async def postTask(self, task: Awaitable):
        tasks = self._chain or [task]
        self._chain = asyncio.gather(tasks)
        return self._chain
