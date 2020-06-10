#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tracing module."""

from pathlib import Path
from typing import Sequence, Union

from pyppeteer import helpers
from pyppeteer.connection import CDPSession


class Tracing:
    """Tracing class.

    You can use :meth:`start` and :meth:`stop` to create a trace file which can
    be opened in Chrome DevTools or
    `timeline viewer <https://chromedevtools.github.io/timeline-viewer/>`_.

    .. code::

        await page.tracing.start({'path': 'trace.json'})
        await page.goto('https://www.google.com')
        await page.tracing.stop()
    """

    def __init__(self, client: CDPSession) -> None:
        self._client = client
        self._recording = False
        self._path = ''

    async def start(
        self, path: Union[Path, str] = '', screenshots: bool = False, categories: Sequence[str] = None
    ) -> None:
        """Start tracing.

        Only one trace can be active at a time per browser.

        This method accepts the following options:

        * ``path`` (str): A path to write the trace file to.
        * ``screenshots`` (bool): Capture screenshots in the trace.
        * ``categories`` (List[str]): Specify custom categories to use instead
          of default.
        """
        defaultCategories = [
            '-*',
            'devtools.timeline',
            'v8.execute',
            'disabled-by-default-devtools.timeline',
            'disabled-by-default-devtools.timeline.frame',
            'toplevel',
            'blink.console',
            'blink.user_timing',
            'latencyInfo',
            'disabled-by-default-devtools.timeline.stack',
            'disabled-by-default-v8.cpu_profiler',
            'disabled-by-default-v8.cpu_profiler.hires',
        ]

        if not isinstance(categories, list):
            try:
                categories = list(categories)
            except TypeError:
                categories = defaultCategories

        if screenshots:
            categories.append('disabled-by-default-devtools.screenshot')

        self._path = path
        self._recording = True
        await self._client.send(
            'Tracing.start', {'transferMode': 'ReturnAsStream', 'categories': ','.join(categories),}
        )

    async def stop(self) -> str:
        """Stop tracing.

        :return: trace data as string.
        """
        contentFuture = self._client.loop.create_future()

        async def complete_trace(event):
            nonlocal self, contentFuture
            result = await helpers.readProtocolStream(self._client, event['stream'], self._path)
            contentFuture.set_result(result)

        self._client.once(
            'Tracing.tracingComplete', complete_trace,
        )
        await self._client.send('Tracing.end')
        self._recording = False
        return await contentFuture
