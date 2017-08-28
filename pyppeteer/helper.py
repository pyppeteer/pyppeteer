#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
from typing import Any, Callable, Dict, List

from pyee import EventEmitter

from pyppeteer.connection import Session


def evaluationString(fun: str, *args: str) -> str:
    _args = ', '.join([json.dumps(arg) for arg in args])
    expr = f'({fun})({_args})'
    return expr


def addEventListener(emitter: EventEmitter, eventName: str, handler: Callable
                     ) -> Dict[str, Any]:
    emitter.on(eventName, handler)
    return {'emitter': emitter, 'eventName': eventName, 'handler': handler}


def removeEventListeners(listeners: List[dict]) -> None:
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


async def serializeRemoteObject(client: Session, remoteObject: dict) -> dict:
    if 'unserializableValue' in remoteObject:
        unserializableValue = remoteObject.get('unserializableValue')
        if unserializableValue in unserializableValueMap:
            return unserializableValueMap[unserializableValue]
        else:
            raise Exception(
                'Unsupported unserializable value: ' + unserializableValue
            )

    objectId = remoteObject.get('objectId')
    if not objectId:
        return remoteObject.get('value')

    subtype = remoteObject.get('subtype')
    if subtype == 'promise':
        return remoteObject.get('description')
    try:
        response = await (await client.send('Runtime.callFunctionOn', {
            'objectId': objectId,
            'functionDeclaration': 'function() { return this; }',
            'returnByValue': True,
        }))
        return response.get('result', {'value': None}).get('value')
    except:
        # Return description for unserializable object, e.g. 'window'.
        return remoteObject.get('description')
    finally:
        await releaseObject(client, remoteObject)


async def releaseObject(client, remoteObject) -> None:
    objectId = remoteObject.get('objectId')
    if not objectId:
        return
    try:
        await client.send('Runtime.releaseObject', {
            'objectId': objectId
        })
    except:
        # Exceptions might happen in case of a page been navigated or closed.
        # Swallow these since they are harmless and we don't leak anything in this case.  # noqa
        pass
