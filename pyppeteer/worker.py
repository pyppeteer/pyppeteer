#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Worker module."""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from pyee import AsyncIOEventEmitter
from pyppeteer.execution_context import ExecutionContext
from pyppeteer.jshandle import JSHandle
from pyppeteer.models import JSFunctionArg

if TYPE_CHECKING:
    from pyppeteer.connection import CDPSession

logger = logging.getLogger(__name__)


class Worker(AsyncIOEventEmitter):
    """The Worker class represents a WebWorker.

    The events `workercreated` and `workerdestroyed` are emitted on the page
    object to signal the worker lifecycle.

    .. code::

        page.on('workercreated', lambda worker: print('Worker created:', worker.url))
    """

    def __init__(
        self,
        client: 'CDPSession',
        url: str,
        consoleAPICalled: Callable[[str, List[JSHandle], Any], None],
        exceptionThrown: Callable[[Dict], None],
    ) -> None:
        super().__init__()
        self._client = client
        self._url = url
        self.loop = client.loop
        self._executionContextPromise = self.loop.create_future()

        def jsHandleFactory(remoteObject: Dict) -> JSHandle:
            return None  # type: ignore

        def onExecutionContentCreated(event: Dict) -> None:
            nonlocal jsHandleFactory

            # noinspection PyRedeclaration
            def jsHandleFactory(remoteObject: Dict) -> JSHandle:
                return JSHandle(executionContext, client, remoteObject)

            executionContext = ExecutionContext(client, event['context'], None)
            self._executionContextCallback(executionContext)

        self._client.once('Runtime.executionContextCreated', onExecutionContentCreated)
        try:
            # This might fail if the target is closed before we receive all
            # execution contexts.
            self._client.send('Runtime.enable', {})
        except Exception as e:
            logger.error(f'An exception occurred: {e}')

        def onConsoleAPICalled(event: Dict[str, Any]) -> None:
            args: List[JSHandle] = []
            for arg in event.get('args', []):
                args.append(jsHandleFactory(arg))
            consoleAPICalled(event['type'], args, event['stackTrace'])

        self._client.on('Runtime.consoleAPICalled', onConsoleAPICalled)
        self._client.on(
            'Runtime.exceptionThrown', lambda exception: exceptionThrown(exception['exceptionDetails']),
        )

    def _executionContextCallback(self, value: ExecutionContext) -> None:
        self._executionContextPromise.set_result(value)

    @property
    def url(self) -> str:
        """Return URL."""
        return self._url

    @property
    async def executionContext(self) -> ExecutionContext:
        """Return ExecutionContext."""
        return await self._executionContextPromise

    async def evaluate(self, pageFunction: str, *args: JSFunctionArg) -> Any:
        """Evaluate ``pageFunction`` with ``args``.

        Shortcut for ``(await worker.executionContext).evaluate(pageFunction, *args)``.
        """
        return await (await self._executionContextPromise).evaluate(pageFunction, *args)

    async def evaluateHandle(self, pageFunction: str, *args: JSFunctionArg) -> JSHandle:
        """Evaluate ``pageFunction`` with ``args`` and return :class:`~pyppeteer.execution_context.JSHandle`.

        Shortcut for ``(await worker.executionContext).evaluateHandle(pageFunction, *args)``.
        """
        return await (await self._executionContextPromise).evaluateHandle(pageFunction, *args)
