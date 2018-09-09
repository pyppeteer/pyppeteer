#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Worker module."""

import logging
from typing import Callable, Dict, List, TYPE_CHECKING

from pyee import EventEmitter

from pyppeteer.execution_context import ExecutionContext, JSHandle

if TYPE_CHECKING:
    from pyppeteer.connection import CDPSession  # noqa: F401

logger = logging.getLogger(__name__)


class Worker(EventEmitter):
    """The Worker class represents a WebWorker.

    The events `workercreated` and `workerdestroyed` are emitted on the page
    object to signal the worker lifecycle.

    .. code::

        page.on('workercreated', lambda worker: print('Worker created:', worker.url))
    """  # noqa: E501

    def __init__(self, client: 'CDPSession', url: str, logEntryAdded: Callable
                 ) -> None:
        super().__init__()
        self._client = client
        self._url = url
        self._loop = client._loop
        self._executionContextPromise = self._loop.create_future()

        def _on_execution_content_created(event: Dict) -> None:
            _execution_contexts: List[ExecutionContext] = []

            def jsHandleFactory(remoteObject: Dict) -> JSHandle:
                executionContext = _execution_contexts.pop()
                return JSHandle(executionContext, client, remoteObject)

            executionContext = ExecutionContext(
                client, event['context'], jsHandleFactory)
            _execution_contexts.append(executionContext)
            self._executionContextCallback(executionContext)

        self._client.on('Runtime.executionContextCreated',
                        _on_execution_content_created)
        self._loop.create_task(self._client.send('Runtime.enable', {}))

        self._client.on('Log.entryAdded', logEntryAdded)
        self._loop.create_task(self._client.send('Log.enable', {}))

    def _executionContextCallback(self, value: ExecutionContext) -> None:
        self._executionContextPromise.set_result(value)

    @property
    def url(self) -> str:
        """Return URL."""
        return self._url

    async def executionContext(self) -> ExecutionContext:
        """Return ExecutionContext."""
        return await self._executionContextPromise
