#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Element handle module."""

import logging
import os.path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# from pyppeteer import helper
from pyppeteer.connection import CDPSession
from pyppeteer.execution_context import ExecutionContext, JSHandle
from pyppeteer.errors import ElementHandleError, NetworkError
from pyppeteer.util import merge_dict

if TYPE_CHECKING:
    from pyppeteer.frame_manager import Frame  # noqa: F401
    # from pyppeteer.page import Page  # noqa: F401


logger = logging.getLogger(__name__)


class ElementHandle(JSHandle):
    """ElementHandle class.

    This class represents an in-page DOM element. ElementHandle can be created
    by the :meth:`pyppeteer.page.Page.querySelector` method.

    ElementHandle prevents DOM element from garbage collection unless the
    handle is disposed. ElementHandles are automatically disposed when their
    origin frame gets navigated.

    ElementHandle isinstance can be used as arguments in
    :meth:`pyppeteer.page.Page.querySelectorEval` and
    :meth:`pyppeteer.page.Page.evaluate` methods.
    """

    def __init__(self, context: ExecutionContext, client: CDPSession,
                 remoteObject: dict, page: Any) -> None:
        super().__init__(context, client, remoteObject)
        self._client = client
        self._remoteObject = remoteObject
        self._page = page
        self._disposed = False

    def asElement(self) -> 'ElementHandle':
        """Return this ElementHandle."""
        return self

    async def _scrollIntoViewIfNeeded(self) -> None:
        error = await self.executionContext.evaluate(
            '''element => {
                if (!element.isConnected)
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
        if not box:
            raise ElementHandleError('Node is not visible.')
        return {
            'x': box['x'] + box['width'] / 2,
            'y': box['y'] + box['height'] / 2,
        }

    async def hover(self) -> None:
        """Move mouse over to center of this element.

        If needed, this method scrolls eleemnt into view. If this element is
        detached from DOM tree, the method raises an ``ElementHandleError``.
        """
        obj = await self._visibleCenter()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        await self._page.mouse.move(x, y)

    async def click(self, options: dict = None, **kwargs: Any) -> None:
        """Click the center of this element.

        If needed, this method scrolls element into view. If the element is
        detached from DOM, the method raises ``ElementHandleError``.

        ``options`` can contain the following fields:

        * ``button`` (str): ``left``, ``right``, of ``middle``, defaults to
          ``left``.
        * ``clickCount`` (int): Defaults to 1.
        * ``delay`` (int|float): Time to wait between ``mousedown`` and
          ``mouseup`` in milliseconds. Defaults to 0.
        """
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
        """Tap the center of this element.

        If needed, this method scrolls element into view. If the element is
        detached from DOM, the method raises ``ElementHandleError``.
        """
        center = await self._visibleCenter()
        x = center.get('x', 0)
        y = center.get('y', 0)
        await self._page.touchscreen.tap(x, y)

    async def focus(self) -> None:
        """Focus on this element."""
        await self.executionContext.evaluate(
            'element => element.focus()', self)

    async def type(self, text: str, options: Dict = None, **kwargs: Any
                   ) -> None:
        """Focus the element and then type text.

        Details see :meth:`pyppeteer.input.Keyboard.type` method.
        """
        options = merge_dict(options, kwargs)
        await self.focus()
        await self._page.keyboard.type(text, options)

    async def press(self, key: str, options: Dict = None, **kwargs: Any
                    ) -> None:
        """Press ``key`` onto the element.

        This method focuses the element, and then uses
        :meth:`pyppeteer.input.keyboard.down` and
        :meth:`pyppeteer.input.keyboard.up`.

        :arg str key: Name of key to press, such as ``ArrowLeft``.

        This method accepts the following options:

        * ``text`` (str): If specified, generates an input event with this
          text.
        * ``delay`` (int|float): Time to wait between ``keydown`` and
          ``keyup``. Defaults to 0.
        """
        options = merge_dict(options, kwargs)
        await self.focus()
        await self._page.keyboard.press(key, options)

    async def boundingBox(self) -> Optional[Dict[str, float]]:
        """Return bounding box of this element.

        If the element is not visible, return ``None``.

        This method returns dictionary of bounding box, which contains:

        * ``x`` (int): The X coordinate of the element in pixels.
        * ``y`` (int): The Y coordinate of the element in pixels.
        * ``width`` (int): The width of the element in pixels.
        * ``height`` (int): The height of the element in pixels.
        """
        try:
            result: Optional[Dict] = await self._client.send(
                'DOM.getBoxModel',
                {'objectId': self._remoteObject.get('objectId')},
            )
        except NetworkError:
            result = None

        if not result:
            return None

        quad = result['model']['border']
        x = min(quad[0], quad[2], quad[4], quad[6])
        y = min(quad[1], quad[3], quad[5], quad[7])
        width = max(quad[0], quad[2], quad[4], quad[6]) - x
        height = max(quad[1], quad[3], quad[5], quad[7]) - y
        return {'x': x, 'y': y, 'width': width, 'height': height}

    async def screenshot(self, options: Dict = None, **kwargs: Any) -> bytes:
        """Take a screenshot of this element.

        If the element is detached from DOM, this method raises an
        ``ElementHandleError``.

        Available options are same as :meth:`pyppeteer.page.Page.screenshot`.
        """
        options = merge_dict(options, kwargs)
        await self._scrollIntoViewIfNeeded()
        _obj = await self._client.send('Page.getLayoutMetrics')
        pageX = _obj['layoutViewport']['pageX']
        pageY = _obj['layoutViewport']['pageY']

        clip = await self.boundingBox()
        if not clip:
            raise ElementHandleError('Node is not visible.')

        clip['x'] = clip['x'] + pageX
        clip['y'] = clip['y'] + pageY
        opt = {'clip': clip}
        opt.update(options)
        return await self._page.screenshot(opt)

    async def querySelector(self, selector: str) -> Optional['ElementHandle']:
        """Return first element which matches ``selector`` under this element.

        If no element mathes the ``selector``, returns ``None``.
        """
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
        """Return all elements which match ``selector`` under this element.

        If no element matches the ``selector``, returns empty list (``[]``).
        """
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

    #: alias to :meth:`querySelector`
    J = querySelector
    #: alias to :meth:`querySelectorAll`
    JJ = querySelectorAll

    async def xpath(self, expression: str) -> List['ElementHandle']:
        """Evaluate XPath expression relative to this elementHandle.

        If there is no such element, return None.

        :arg str expression: XPath string to be evaluated.
        """
        arrayHandle = await self.executionContext.evaluateHandle(
            '''(element, expression) => {
                const document = element.ownerDocument || element;
                const iterator = document.evaluate(expression, element, null,
                    XPathResult.ORDERED_NODE_ITERATOR_TYPE);
                const array = [];
                let item;
                while ((item = iterator.iterateNext()))
                    array.push(item);
                return array;

            }''', self, expression)
        properties = await arrayHandle.getProperties()
        await arrayHandle.dispose()
        result = []
        for property in properties.values():
            elementHandle = property.asElement()
            if elementHandle:
                result.append(elementHandle)
        return result

    #: alias to :meth:`xpath`
    Jx = xpath
