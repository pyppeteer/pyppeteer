#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Helper functions."""

import json
import math
from typing import Any, Callable, Dict, List

from pyee import EventEmitter

from pyppeteer.connection import CDPSession
from pyppeteer.errors import ElementHandleError


def evaluationString(fun: str, *args: Any) -> str:
    """Convert function and arguments to str."""
    _args = ', '.join([
        json.dumps('undefined' if arg is None else arg) for arg in args
    ])
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


def valueFromRemoteObject(remoteObject: Dict) -> Any:
    """Serialize value of remote object."""
    if remoteObject.get('objectId'):
        raise ElementHandleError('Cannot extract value when objectId is given')
    value = remoteObject.get('unserializableValue')
    if value:
        if value == '-0':
            return -0
        elif value == 'NaN':
            return None
        elif value == 'Infinity':
            return math.inf
        elif value == '-Infinity':
            return -math.inf
        else:
            raise ElementHandleError(
                'Unsupported unserializable value: {}'.format(value))
    return remoteObject.get('value')


async def releaseObject(client: CDPSession, remoteObject: dict) -> None:
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


def is_jsfunc(func: str) -> bool:  # not in puppeteer
    """Huristically check function or expression."""
    func = func.strip()
    if func.startswith('function') or func.startswith('async '):
        return True
    elif '=>' in func:
        return True
    return False
