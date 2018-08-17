#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio


def waitEvent(emitter, event_name):
    fut = asyncio.get_event_loop().create_future()

    def set_done(*args, **kwargs):
        fut.set_result(True)

    emitter.once(event_name, set_done)
    return fut
