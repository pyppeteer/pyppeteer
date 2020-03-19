#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Execution Context Module."""

import logging
import math
import re
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

from pyppeteer import helpers
from pyppeteer.connection import CDPSession
from pyppeteer.errors import ElementHandleError
from pyppeteer.jshandle import createJSHandle, JSHandle, ElementHandle

if TYPE_CHECKING:
    from pyppeteer.domworld import DOMWorld

logger = logging.getLogger(__name__)

EVALUATION_SCRIPT_URL = '__pyppeteer_evaluation_script__'
SOURCE_URL_REGEX = re.compile(r'^[\040\t]*//[@#] sourceURL=\s*(\S*?)\s*$', re.MULTILINE)


class ExecutionContext(object):
    """Execution Context class."""

    def __init__(self, client: CDPSession, contextPayload: Dict, world: 'DOMWorld') -> None:
        self._client = client
        self._world = world
        self._contextId = contextPayload.get('id')

    @property
    def frame(self) -> Optional['Frame']:
        """Return frame associated with this execution context."""
        if self._world:
            return self._world.frame

    async def evaluate(self, pageFunction: str, *args: Any) -> Any:
        """Execute ``pageFunction`` on this context.

        Details see :meth:`pyppeteer.page.Page.evaluate`.
        """
        return await self._evaluateInternal(True, pageFunction, *args)

    async def evaluateHandle(self, pageFunction: str, *args: Any) -> JSHandle:
        """Execute ``pageFunction`` on this context.
        Details see :meth:`pyppeteer.page.Page.evaluateHandle`.
        """
        return await self._evaluateInternal(True, pageFunction, *args)

    async def _evaluateInternal(self, returnByValue: bool, pageFunction: str, *args):
        suffix = f'//# sourceURL={EVALUATION_SCRIPT_URL}'

        if not helpers.is_js_func(pageFunction):
            try:
                if SOURCE_URL_REGEX.match(pageFunction):
                    expressionWithSourceUrl = pageFunction
                else:
                    expressionWithSourceUrl = f'{pageFunction}\n{suffix}'
                remoteObject = await self._client.send(
                    'Runtime.evaluate',
                    {
                        'expression': expressionWithSourceUrl,
                        'contextId': self._contextId,
                        'returnByValue': returnByValue,
                        'awaitPromise': True,
                        'userGesture': True,
                    },
                )
            except Exception as e:
                exceptionDetails = rewriteError(e)
                raise type(e)(f'Evaluation failed: {helpers.getExceptionMessage(exceptionDetails)}')
        else:
            try:
                remoteObject = await self._client.send(
                    'Runtime.callFunctionOn',
                    {
                        'functionDeclaration': f'{pageFunction}\n{suffix}\n',
                        'executionContextId': self._contextId,
                        'arguments': [self._convertArgument(arg) for arg in args],
                        'returnByValue': returnByValue,
                        'awaitPromise': True,
                        'userGesture': True,
                    },
                )
            except Exception as e:
                exceptionDetails = rewriteError(e)
                raise type(e)(f'Evaluation failed: {helpers.getExceptionMessage(exceptionDetails)}')

        exceptionDetails = remoteObject.get('exceptionDetails')
        if exceptionDetails:
            raise ElementHandleError('Evaluation failed: {}'.format(helpers.getExceptionMessage(exceptionDetails)))

        remoteObject = remoteObject['result']
        if returnByValue:
            return helpers.valueFromRemoteObject(remoteObject)
        else:
            return createJSHandle(self, remoteObject)

    def _convertArgument(self, arg: Any) -> Dict:  # noqa: C901
        if arg == math.inf:
            return {'unserializableValue': 'Infinity'}
        if arg == -math.inf:
            return {'unserializableValue': '-Infinity'}
        objectHandle = arg if isinstance(arg, JSHandle) else None
        if objectHandle:
            if objectHandle._context != self:
                raise ElementHandleError(
                    'JSHandles can be evaluated only in the context they were created!'
                )  # noqa: E501
            if objectHandle._disposed:
                raise ElementHandleError('JSHandle is disposed!')
            if objectHandle._remoteObject.get('unserializableValue'):
                return {'unserializableValue': objectHandle._remoteObject.get('unserializableValue')}  # noqa: E501
            if not objectHandle._remoteObject.get('objectId'):
                return {'value': objectHandle._remoteObject.get('value')}
            return {'objectId': objectHandle._remoteObject.get('objectId')}
        return {'value': arg}

    async def queryObjects(self, prototypeHandle: 'JSHandle'):
        if prototypeHandle._disposed:
            raise ElementHandleError('Prototype JSHandle is disposed')
        if not prototypeHandle._remoteObject.get('objectId'):
            raise ElementHandleError('Prototype JSHandle must not be referencing primitive value')
        response = await self._client.send(
            'Runtime.queryObjects', {'prototypeObjectId': prototypeHandle._remoteObject['objectId']}
        )
        return createJSHandle(context=self, remoteObject=response.get('objects'))

    async def _adoptBackendNodeId(self, backendNodeId: int):
        obj = await self._client.send(
            'DOM.resolveNode', {'backednNodeId': backendNodeId, 'executionContextId': self._contextId}
        )
        return createJSHandle(context=self, remoteObject=obj)

    async def _adoptElementHandle(self, elementHandle: ElementHandle):
        if elementHandle.executionContext() == self:
            raise ElementHandleError('Cannot adopt handle that already belongs to this execution context')
        if not self._world:
            raise ElementHandleError('Cannot adopt handle without DOMWorld')
        nodeInfo = await self._client.send('DOM.describeNode', {'objectId': elementHandle._remoteObject['objectId']})
        return self._adoptBackendNodeId(nodeInfo['node']['backendNodeId'])


def rewriteError(error: Exception) -> Union[None, Dict[str, Dict[str, str]]]:
    msg = error.args[0]
    if 'Object reference chain is too long' in msg:
        return {'result': {'type': 'undefined'}}
    if "Object couldn't be returned by value" in msg:
        return {'result': {'type': 'undefined'}}
    if msg.endswith('Cannot find context with specified id'):
        msg = 'Execution context was destroyed, most likely because of a navigation.'  # noqa: E501
        raise type(error)(msg)
    raise error
