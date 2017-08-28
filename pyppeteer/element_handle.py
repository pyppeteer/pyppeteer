#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os.path
from typing import Dict

from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.input import Mouse


class ElementHandle(object):
    def __init__(self, client: Session, remoteObject: dict, mouse: Mouse
                 ) -> None:
        self._client = client
        self._remoteObject = remoteObject
        self._mouse = mouse
        self._disposed = False

    async def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        await helper.releaseObject(self._client, self._remoteObject)

    async def evaluate(self, pageFunction: str, *args) -> dict:
        if self._disposed:
            raise Exception('ElementHandle is disposed!')
        _args = ['this']
        _args.extend(json.dumps(x) for x in args)
        stringifiedArgs = ','.join(_args)
        functionDeclaration = f'''
function() {{ return ({pageFunction})({stringifiedArgs}) }}
'''
        objectId = self._remoteObject.get('objectId')
        obj = await (await self._client.send(
            'Runtime.callFunctionOn', {
                'objectId': objectId,
                'functionDeclaration': functionDeclaration,
                'returnByValue': False,
                'awaitPromise': True,
            }
        ))
        exceptionDetails = obj.get('exceptionDetails')
        remoteObject = obj.get('result')
        if exceptionDetails:
            raise Exception('Evaluation failed: ' + helper.getExceptionMessage(exceptionDetails))  # noqa: E501
        return await helper.serializeRemoteObject(self._client, remoteObject)

    async def _visibleCenter(self) -> Dict[str, int]:
        center = await self.evaluate('''
element => {
    if (!element.ownerDocument.contains(element))
        return null;
    element.scrollIntoViewIfNeeded();
    let rect = element.getBoundingClientRect();
    return {
        x: (Math.max(rect.left, 0) + Math.min(rect.right, window.innerWidth)) / 2,
        y: (Math.max(rect.top, 0) + Math.min(rect.bottom, window.innerHeight)) / 2
    };
}
        ''')  # noqa: E501
        if not center:
            # raise Exception('No node found for selector: ' + selector)
            raise Exception('No node found for selector: ')
        return center

    async def hover(self) -> None:
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        await self._mouse.move(x, y)

    async def click(self, options: dict = None) -> None:
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        if options is None:
            options = dict()
        await self._mouse.click(x, y, options)

    async def uploadFile(self, *filePaths: str) -> None:
        files = [os.path.abspath(p) for p in filePaths]
        objectId = self._remoteObject.get('objectId')
        return await self._client.send(
            'DOM.setFileInputFiles',
            {'objectId': objectId, 'files': files}
        )
