#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tracing module."""

import asyncio
from pathlib import Path
from typing import Awaitable

from pyppeteer.connection import Session


class Tracing(object):
    """Tracing class."""

    def __init__(self, client: Session) -> None:
        """Make new tracing object."""
        self._client = client
        self._recording = False
        self._path = ''

    async def start(self, options: dict) -> None:
        """Start."""
        categoriesArray = [
            '-*', 'devtools.timeline', 'v8.execute',
            'disabled-by-default-devtools.timeline',
            'disabled-by-default-devtools.timeline.frame', 'toplevel',
            'blink.console', 'blink.user_timing', 'latencyInfo',
            'disabled-by-default-devtools.timeline.stack',
            'disabled-by-default-v8.cpu_profiler',
        ]

        if 'screenshots' in options:
            categoriesArray.append('disabled-by-default-devtools.screenshot')

        self._path = options.get('path', '')
        self._recording = True
        await self._client.send('Tracing.start', {
            'transferMode': 'ReturnAsStream',
            'categories': ','.join(categoriesArray),
        })

    async def stop(self) -> Awaitable:
        """Stop."""
        contentPromise = asyncio.get_event_loop().create_future()
        self._client.once(
            'Tracing.tracingComplete',
            lambda event: asyncio.ensure_future(
                self._readStream(event.get('stream'), self._path)
            ).add_done_callback(
                lambda fut: contentPromise.set_result(
                    fut.result())  # type: ignore
            )
        )
        await self._client.send('Tracing.end')
        self._recording = False
        return contentPromise

    async def _readStream(self, handle: str, path: str) -> None:
        eof = False
        file = Path(path)
        with file.open('w') as f:
            while not eof:
                response = await(await self._client.send('IO.read', {
                    'handle': handle
                }))
                eof = response.get('eof', False)
            if path:
                f.write(response.get('data', ''))
        await self._client.send('IO.close', {'handle': handle})
