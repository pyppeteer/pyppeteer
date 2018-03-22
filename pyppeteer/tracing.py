#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tracing module."""

import asyncio
from pathlib import Path
from typing import Any, Awaitable

from pyppeteer.connection import CDPSession
from pyppeteer.util import merge_dict


class Tracing(object):
    """Tracing class."""

    def __init__(self, client: CDPSession) -> None:
        self._client = client
        self._recording = False
        self._path = ''

    async def start(self, options: dict = None, **kwargs: Any) -> None:
        """Start tracing.

        Only one trace can be active at a time per browser.

        This method accepts the following options:

        * ``path`` (str): A path to write the trace file to. **required**
        * ``screenshots`` (bool): Capture screenshots in the trace.
        * ``categories`` (List[str]): Specify custom categories to use instead
          of default.
        """
        options = merge_dict(options, kwargs)
        defaultCategories = [
            '-*', 'devtools.timeline', 'v8.execute',
            'disabled-by-default-devtools.timeline',
            'disabled-by-default-devtools.timeline.frame', 'toplevel',
            'blink.console', 'blink.user_timing', 'latencyInfo',
            'disabled-by-default-devtools.timeline.stack',
            'disabled-by-default-v8.cpu_profiler',
        ]
        categoriesArray = options.get('categories', defaultCategories)

        if 'screenshots' in options:
            categoriesArray.append('disabled-by-default-devtools.screenshot')

        self._path = options.get('path', '')
        self._recording = True
        await self._client.send('Tracing.start', {
            'transferMode': 'ReturnAsStream',
            'categories': ','.join(categoriesArray),
        })

    async def stop(self) -> Awaitable:
        """Stop tracing."""
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
        return await contentPromise

    async def _readStream(self, handle: str, path: str) -> None:
        eof = False
        file = Path(path)
        with file.open('w') as f:
            while not eof:
                response = await self._client.send('IO.read', {
                    'handle': handle
                })
                eof = response.get('eof', False)
                if path:
                    f.write(response.get('data', ''))
        await self._client.send('IO.close', {'handle': handle})
