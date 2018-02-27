#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Element handle module."""

import json
import logging
import os.path
from typing import Any, Dict, Optional, TYPE_CHECKING
import warnings

from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.errors import ElementHandleError, BrowserError
from pyppeteer.input import Mouse, Touchscreen

if TYPE_CHECKING:
    from pyppeteer.frame_manager import Frame  # noqa: F401


logger = logging.getLogger(__name__)


class ElementHandle(object):
    """ElementHandle class."""

    def __init__(self, frame: Any, client: Session, remoteObject: dict,
                 mouse: Mouse, touchscreen: Touchscreen) -> None:
        """Make new element handle object."""
        self._frame: Frame = frame
        self._client = client
        self._remoteObject = remoteObject
        self._mouse = mouse
        self._touchscreen = touchscreen
        self._disposed = False

    def _remoteObjectId(self) -> Optional[str]:
        return None if self._disposed else self._remoteObject['objectId']

    async def dispose(self) -> None:
        """Release element handle."""
        if self._disposed:
            return
        self._disposed = True
        await helper.releaseObject(self._client, self._remoteObject)

    async def evaluate(self, pageFunction: str, *args: Any) -> Any:
        """[Deprecated] Evaluate the pageFunction on browser."""
        deprecation_msg = (
            'ElementHandle.evaluate is dropped in puppeteer. '
            'Use Page.evaluate(..., ElementHandle) instead.'
        )
        logger.warning('[DEPRECATED] ' + deprecation_msg)
        warnings.warn(deprecation_msg, DeprecationWarning)

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
        center = await self._frame.evaluate('''
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
        ''', self)  # noqa: E501
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

    async def click(self, options: dict = None, **kwargs: Any) -> None:
        """Click this element."""
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        if options is None:
            options = dict()
        options.update(kwargs)
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
        """[Deprecated] Get attribute value of the `key` of this element."""
        deprecation_msg = (
            'ElementHandle.attribute is dropped in puppeteer. '
            'Use Page.querySelectorEval or Page.Jeval instead.'
        )
        logger.warning('[DEPRECATED]' + deprecation_msg)
        warnings.warn(deprecation_msg, DeprecationWarning)
        return await self.evaluate(
            '(element, key) => element.getAttribute(key)', key)

    async def tap(self) -> None:
        """Tap this element."""
        center = await self._visibleCenter()
        x = center.get('x', 0)
        y = center.get('y', 0)
        await self._touchscreen.tap(x, y)
