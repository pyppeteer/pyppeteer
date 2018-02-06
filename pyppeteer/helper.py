#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Helper functions."""

import json
import math
from typing import Any, Callable, Dict, List

from pyee import EventEmitter

from pyppeteer.connection import Session


def evaluationString(fun: str, *args: Any) -> str:
    """Convert function and arguments to str."""
    _args = ', '.join([json.dumps(arg) for arg in args])
    expr = f'({fun})({_args})'
    return expr


def getExceptionMessage(exceptionDetails: dict) -> str:
    """Get exception message from `exceptionDetails` object."""
    exception = exceptionDetails.get('exception')
    if exception:
        return exception.get('description')
    message = exceptionDetails.get('text', '')
    stackTrace = exceptionDetails.get('stackTrace', dict())
    if stackTrace:
        for callframe in stackTrace.get('callFrames'):
            location = (callframe.get('url', '') + ':' +
                        callframe.get('lineNumber', '') + ':' +
                        callframe.get('columnNumber'))
            functionName = callframe.get('functionName', '<anonymous>')
            message = message + f'\n    at {functionName} ({location})'
    return message


def addEventListener(emitter: EventEmitter, eventName: str, handler: Callable
                     ) -> Dict[str, Any]:
    """Add handler to the emitter and return emitter/handler."""
    emitter.on(eventName, handler)
    return {'emitter': emitter, 'eventName': eventName, 'handler': handler}


def removeEventListeners(listeners: List[dict]) -> None:
    """Remove listeners from emitter."""
    for listener in listeners:
        emitter = listener['emitter']
        eventName = listener['eventName']
        handler = listener['handler']
        emitter.remove_listener(eventName, handler)
    listeners.clear()


unserializableValueMap = {
    '-0': -0,
    'NaN': None,
    None: None,
    'Infinity': math.inf,
    '-Infinity': -math.inf,
}


async def serializeRemoteObject(client: Session, remoteObject: dict) -> Any:
    """Serialize remote object."""
    if 'unserializableValue' in remoteObject:
        unserializableValue = remoteObject.get('unserializableValue')
        if unserializableValue in unserializableValueMap:
            return unserializableValueMap[unserializableValue]
        else:
            # BrowserError may be better
            raise ValueError(
                'Unsupported unserializable value: ' + str(unserializableValue)
            )

    objectId = remoteObject.get('objectId')
    if not objectId:
        return remoteObject.get('value')

    subtype = remoteObject.get('subtype')
    if subtype == 'promise':
        return remoteObject.get('description')
    try:
        response = await client.send('Runtime.callFunctionOn', {
            'objectId': objectId,
            'functionDeclaration': 'function() { return this; }',
            'returnByValue': True,
        })
        return response.get('result', {}).get('value')
    except Exception:
        # Return description for unserializable object, e.g. 'window'.
        return remoteObject.get('description')
    finally:
        await releaseObject(client, remoteObject)


async def releaseObject(client: Session, remoteObject: dict) -> None:
    """Release remote object."""
    objectId = remoteObject.get('objectId')
    if not objectId:
        return
    try:
        await client.send('Runtime.releaseObject', {
            'objectId': objectId
        })
    except Exception:
        # Exceptions might happen in case of a page been navigated or closed.
        # Swallow these since they are harmless and we don't leak anything in this case.  # noqa
        pass


def get_positive_int(obj: dict, name: str) -> int:
    """Get and check the value of name in obj is positive integer."""
    value = obj[name]
    if not isinstance(value, int):
        raise TypeError(
            f'{name} must be integer: {type(value)}')
    elif value < 0:
        raise ValueError(
            f'{name} must be positive integer: {value}')
    return value
