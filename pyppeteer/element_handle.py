#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Element handle module."""

import logging
import os.path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.execution_context import ExecutionContext, JSHandle
from pyppeteer.errors import ElementHandleError
from pyppeteer.util import merge_dict

if TYPE_CHECKING:
    from pyppeteer.frame_manager import Frame  # noqa: F401
    # from pyppeteer.page import Page  # noqa: F401


logger = logging.getLogger(__name__)


class ElementHandle(JSHandle):
    """ElementHandle class."""

    def __init__(self, context: ExecutionContext, client: Session,
                 remoteObject: dict, page: Any) -> None:
        """Make new element handle object."""
        super().__init__(context, client, remoteObject)
        self._client = client
        self._remoteObject = remoteObject
        self._page = page
        self._disposed = False

    def asElement(self) -> 'ElementHandle':
        """Return as an element handle."""
        return self

    async def _scrollIntoViewIfNeeded(self) -> None:
        error = await self.executionContext.evaluate(
            '''element => {
                if (!element.ownerDocument.contains(element))
                    return 'Node is detached from document';
                if (element.nodeType !== Node.ELEMENT_NODE)
                    return 'Node is not of type HTMLElement';
                element.scrollIntoViewIfNeeded();
                return false;
            }''', self)
        if error:
            raise ElementHandleError(error)

    async def _visibleCenter(self) -> Dict[str, float]:
        await self._scrollIntoViewIfNeeded()
        box = await self.boundingBox()
        return {
            'x': box['x'] + box['width'] / 2,
            'y': box['y'] + box['height'] / 2,
        }

    async def hover(self) -> None:
        """Move mouse over this element."""
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        await self._page.mouse.move(x, y)

    async def click(self, options: dict = None, **kwargs: Any) -> None:
        """Click this element."""
        options = merge_dict(options, kwargs)
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        await self._page.mouse.click(x, y, options)

    async def uploadFile(self, *filePaths: str) -> dict:
        """Upload files."""
        files = [os.path.abspath(p) for p in filePaths]
        objectId = self._remoteObject.get('objectId')
        return await self._client.send(
            'DOM.setFileInputFiles',
            {'objectId': objectId, 'files': files}
        )

    async def tap(self) -> None:
        """Tap this element."""
        center = await self._visibleCenter()
        x = center.get('x', 0)
        y = center.get('y', 0)
        await self._page.touchscreen.tap(x, y)

    async def focus(self) -> None:
        """Focus this element."""
        await self.executionContext.evaluate(
            'element => element.focus()', self)

    async def type(self, text: str, options: Dict = None, **kwargs: Any
                   ) -> None:
        """Type characters on this element."""
        options = merge_dict(options, kwargs)
        await self.focus()
        await self._page.keyboard.type(text, options)

    async def press(self, key: str, options: Dict = None, **kwargs: Any
                    ) -> None:
        """Type key on this element."""
        options = merge_dict(options, kwargs)
        await self.focus()
        await self._page.keyboard.press(key, options)

    async def boundingBox(self) -> Dict[str, float]:
        """Return bounding box size of this node."""
        _obj = await self._client.send('DOM.getBoxModel', {
            'objectId': self._remoteObject.get('objectId'),
        })
        model = _obj.get('model')
        if not model:
            raise ElementHandleError('node is detached from document')

        quad = model['border']
        x = min(quad[0], quad[2], quad[4], quad[6])
        y = min(quad[1], quad[3], quad[5], quad[7])
        width = max(quad[0], quad[2], quad[4], quad[6]) - x
        height = max(quad[1], quad[3], quad[5], quad[7]) - y
        return {'x': x, 'y': y, 'width': width, 'height': height}

    async def screenshot(self, options: Dict = None, **kwargs: Any) -> bytes:
        """Take a screenshot of this element."""
        options = merge_dict(options, kwargs)
        await self._scrollIntoViewIfNeeded()
        boundingBox = await self.boundingBox()
        opt = {'clip': boundingBox}
        opt.update(options)
        return await self._page.screenshot(opt)

    async def querySelector(self, selector: str) -> Optional['ElementHandle']:
        """Return first element which matches `selector`."""
        handle = await self.executionContext.evaluateHandle(
            '(element, selector) => element.querySelector(selector)',
            self, selector,
        )
        element = handle.asElement()
        if element:
            return element
        await handle.dispose()
        return None

    async def querySelectorAll(self, selector: str) -> List['ElementHandle']:
        """Return all elements which match `selector`."""
        arrayHandle = await self.executionContext.evaluateHandle(
            '(element, selector) => element.querySelectorAll(selector)',
            self, selector,
        )
        properties = await arrayHandle.getProperties()
        await arrayHandle.dispose()
        result = []
        for prop in properties.values():
            elementHandle = prop.asElement()
            if elementHandle:
                result.append(elementHandle)
        return result  # type: ignore

    #: alias to querySelector
    J = querySelector
    #: alias to querySelectorAll
    JJ = querySelectorAll
