#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Element handle module."""

import json
import os.path
from typing import Any, Dict

from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.errors import ElementHandleError, BrowserError
from pyppeteer.input import Mouse


class ElementHandle(object):
    """ElementHandle class."""

    def __init__(self, client: Session, remoteObject: dict, mouse: Mouse
                 ) -> None:
        """Make new element handle object."""
        self._client = client
        self._remoteObject = remoteObject
        self._mouse = mouse
        self._disposed = False

    async def dispose(self) -> None:
        """Release element handle."""
        if self._disposed:
            return
        self._disposed = True
        await helper.releaseObject(self._client, self._remoteObject)

    async def evaluate(self, pageFunction: str, *args: Any) -> Any:
        """Evaluate the pageFunction on browser."""
        if self._disposed:
            raise ElementHandleError('ElementHandle is disposed!')
        _args = ['this']
        _args.extend(json.dumps(x) for x in args)
        stringifiedArgs = ','.join(_args)
        functionDeclaration = f'''
function() {{ return ({pageFunction})({stringifiedArgs}) }}
'''
        objectId = self._remoteObject.get('objectId')
        obj = await self._client.send(
            'Runtime.callFunctionOn', {
                'objectId': objectId,
                'functionDeclaration': functionDeclaration,
                'returnByValue': False,
                'awaitPromise': True,
            }
        )
        exceptionDetails = obj.get('exceptionDetails', dict())
        remoteObject = obj.get('result', dict())
        if exceptionDetails:
            raise BrowserError(
                'Evaluation failed: ' +
                helper.getExceptionMessage(exceptionDetails)
            )
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
            raise BrowserError('No node found for selector: ')
        return center

    async def hover(self) -> None:
        """Move mouse over this element."""
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        await self._mouse.move(x, y)

    async def click(self, options: dict = None) -> None:
        """Click this element."""
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        if options is None:
            options = dict()
        await self._mouse.click(x, y, options)

    async def uploadFile(self, *filePaths: str) -> dict:
        """Upload files."""
        files = [os.path.abspath(p) for p in filePaths]
        objectId = self._remoteObject.get('objectId')
        return await self._client.send(
            'DOM.setFileInputFiles',
            {'objectId': objectId, 'files': files}
        )

    async def attribute(self, key: str) -> str:
        """Get attribute value of the `key` of this element."""
        return await self.evaluate(
            '(element, key) => element.getAttribute(key)', key)
