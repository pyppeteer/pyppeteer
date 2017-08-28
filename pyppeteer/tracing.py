#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from pathlib import Path

from pyppeteer.connection import Session


class Tracing(object):
    def __init__(self, client: Session) -> None:
        self._client = client
        self._recording = False
        self._path = ''

    async def start(self, options: dict) -> None:
        categoriesArray = [
            '-*', 'devtools.timeline', 'v8.execute',
            'disabled-by-default-devtools.timeline',
            'disabled-by-default-devtools.timeline.frame', 'toplevel',
            'blink.console', 'blink.user_timing', 'latencyInfo',
            'disabled-by-default-devtools.timeline.stack',
            'disabled-by-default-v8.cpu_profiler',
        ]

        if 'screenshots' in options:
            categoriesArray.push('disabled-by-default-devtools.screenshot')

        self._path = options.get('path')
        self._recording = True
        await self._client.send('Tracing.start', {
            'transferMode': 'ReturnAsStream',
            'categories': categoriesArray.join(','),
        })

    async def stop(self) -> None:
        contentPromise = asyncio.get_event_loop().create_future()
        self._client.once(
            'Tracing.tracingComplete',
            lambda event: asyncio.ensure_future(
                self._readStream(event.get('stream'), self._path)
            ).add_done_callback(
                lambda fut: contentPromise.set_result(fut.result())
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
                response = await self._client.send('IO.read', {'handle': handle})  # noqa: E501
                eof = response.get('eof')
            if path:
                f.write(response.get('data', ''))
        await self._client.send('IO.close', {'handle': handle})
