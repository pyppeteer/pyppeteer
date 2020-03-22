#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from asyncio.futures import Future
from asyncio.tasks import Task
from typing import Awaitable, List, Union

from pyppeteer.errors import TimeoutError


def waitEvent(emitter, event_name):
    fut = asyncio.get_event_loop().create_future()

    def set_done(arg=None):
        fut.set_result(arg)

    emitter.once(event_name, set_done)
    return fut


def gather_with_timeout(*aws: Awaitable, timeout: float = 10, **kwargs) -> Awaitable[List[Union[Task, Future]]]:
    async def timeout_func(after: float) -> None:
        await asyncio.sleep(after)
        raise TimeoutError('timeout error occurred while gathering awaitables')

    return asyncio.gather(*[*aws, timeout_func(timeout)], **kwargs)
