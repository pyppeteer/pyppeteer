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
    """
    Similar to asyncio.gather, but with one key difference: It will timeout. A wrapped asyncio.gather approach was
    chosen over asyncio.wait or asyncio.wait_for, etc. because asyncio.gather returns the awaitables in the same order
    that they were passed in, which allows for closer analogous behaviour to JS's Promise.all
    :param aws: Awaitables to gather
    :param timeout: amount of time to wait, in seconds, before raising timeout error
    :param kwargs: kwargs to pass to asyncio.gather
    :return: same as asyncio.gather
    """
    async def timeout_func(after: float) -> None:
        await asyncio.sleep(after)
        raise TimeoutError('timeout error occurred while gathering awaitables')

    return asyncio.gather(*[*aws, timeout_func(timeout)], **kwargs)
