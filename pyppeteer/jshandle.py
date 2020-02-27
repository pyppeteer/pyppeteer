import asyncio
import copy
import math
import os
from typing import Dict, Optional, List, Any

from pyppeteer import helper
from pyppeteer.errors import BrowserError, ElementHandleError
from pyppeteer.helper import debugError
from pyppeteer.util import merge_dict


def createJSHandle(context, remoteObject):
    frame = context.frame()
    if remoteObject.get('subtype') == 'node' and frame:
        frameManager = frame._frameManager
        return ElementHandle(
            context, context._client, remoteObject, frameManager.page(), frameManager
        )
    return JSHandle(
        context,
        context._client,
        remoteObject,
    )


class JSHandle(object):
    """JSHandle class.

    JSHandle represents an in-page JavaScript object. JSHandle can be created
    with the :meth:`~pyppeteer.page.Page.evaluateHandle` method.
    """

    def __init__(
            self,
            context: 'ExecutionContext',
            client: 'CDPSession',
            remoteObject: 'RemoteObject'
    ):
        self._context = context
        self._client = client
        self._remoteObject = remoteObject
        self._disposed = False

    @property
    def executionContext(self):
        """Get execution context of this handle."""
        return self._context

    async def evaluate(self, pageFunction: str, *args):
        return await self.executionContext.evaluate(pageFunction, *args)

    async def evaluateHandle(self, pageFunction: str, *args):
        return await self.executionContext.evaluateHandle(pageFunction, *args)

    async def getProperty(self, propertyName: str) -> 'JSHandle':
        """Get property value of ``propertyName``."""
        objectHandle = await self._context.evaluateHandle(
            '''(object, propertyName) => {
                const result = {__proto__: null};
                result[propertyName] = object[propertyName];
                return result;
            }''', self, propertyName)
        properties = await objectHandle.getProperties()
        result = properties[propertyName]
        await objectHandle.dispose()
        return result

    async def getProperties(self) -> Dict[str, 'JSHandle']:
        """Get all properties of this handle."""
        response = await self._client.send('Runtime.getProperties', {
            'objectId': self._remoteObject.get('objectId', ''),
            'ownProperties': True,
        })
        result = dict()
        for prop in response['result']:
            if not prop.get('enumerable'):
                continue
            result[prop.get('name')] = createJSHandle(self._context, prop.get('value'))
        return result

    async def jsonValue(self) -> Dict:
        """Get Jsonized value of this object."""
        objectId = self._remoteObject.get('objectId')
        if objectId:
            response = await self._client.send(
                'Runtime.callFunctionOn',
                {
                    'functionDeclaration': 'function() { return this; }',
                    'objectId': objectId,
                    'returnByValue': True,
                    'awaitPromise': True,
                })
            return helper.valueFromRemoteObject(response['result'])
        return helper.valueFromRemoteObject(self._remoteObject)

    def asElement(self) -> Optional['ElementHandle']:
        """Return either null or the object handle itself."""
        return None

    async def dispose(self) -> None:
        """Stop referencing the handle."""
        if self._disposed:
            return
        self._disposed = True
        await helper.releaseObject(self._client, self._remoteObject)

    def toString(self) -> str:
        """Get string representation."""
        if self._remoteObject.get('objectId'):
            _type = self._remoteObject.get('subtype') or self._remoteObject.get('type')
            return f'JSHandle@{_type}'
        return 'JSHandle:{}'.format(helper.valueFromRemoteObject(self._remoteObject))


class ElementHandle(JSHandle):

    def __init__(
            self,
            context: 'ExecutionContext',
            client: 'CDPSession',
            remoteObject: 'RemoteObject',
            page: 'Page',
            frameManager: 'FrameManager',
    ):
        super().__init__(context, client, remoteObject)
        self._page = page
        self._frameManager = frameManager
        self._disposed = False

    def asElement(self) -> Optional['ElementHandle']:
        return self

    async def contentFrame(self):
        nodeInfo = await self._client.send(
            'DOM.describeNode',
            {
                'objectId': self._remoteObject.get('objectId')
            }
        )
        frameId = nodeInfo.get('node', {}).get('frameId')
        if not isinstance(frameId, str):
            return
        return self._frameManager.frame(frameId)

    async def _scrollIntoViewIfNeeded(self):
        error = await self.evaluate(
            """
            async(element, pageJavascriptEnabled) => {
              if (!element.isConnected)
                return 'Node is detached from document';
              if (element.nodeType !== Node.ELEMENT_NODE)
                return 'Node is not of type HTMLElement';
              // force-scroll if page's javascript is disabled.
              if (!pageJavascriptEnabled) {
                element.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});
                return false;
              }
              const visibleRatio = await new Promise(resolve => {
                const observer = new IntersectionObserver(entries => {
                  resolve(entries[0].intersectionRatio);
                  observer.disconnect();
                });
                observer.observe(element);
              });
              if (visibleRatio !== 1.0)
                element.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});
              return false;
            }
            """,
            self._page._javascriptEnabled
        )
        if error:
            raise BrowserError(error)

    async def _clickablePoint(self):
        result, layoutMetrics = await asyncio.gather(
            self._client.send(
                'DOM.getContentQuads',
                {'objectId': self._remoteObject['objectId']}
            ),
            self._client.send('Page.getLayoutMetrics')
        )
        if not result or not result.get('quads', {}).get('length'):
            raise BrowserError('Node is either not visible or not an HTMLEelement')
        clientWidth, clientHeight = layoutMetrics.layoutViewport
        quads = [
            self._fromProtocolQuad(quad)
            for quad in self._intersectQuadWithViewport(quad, clientWidth, clientHeight)
            if computedQuadArea(quad) > 1
        ]
        if not quads:
            raise BrowserError('Node is either not visible or not an HTMLElement')
        quad = quads[0]
        x = 0
        y = 0
        for point in quad:
            x += point.x
            y += point.y
        return {
            'x': x / 4,
            'y': y / 4,
        }

    def _getBoxModel(self):
        try:
            return self._client.send(
                'DOM.getBoxModel', {'objectId': self._remoteObject['objectId']}
            )
        except Exception as e:
            debugError(e)

    def _fromProtocolQuad(self, quad):
        return [
            {'x': quad[0], 'y': quad[1]},
            {'x': quad[2], 'y': quad[3]},
            {'x': quad[4], 'y': quad[5]},
            {'x': quad[6], 'y': quad[7]},
        ]

    def _intersectQuadWithViewport(self, quad, width, height):
        return [
            {
                'x': min(max(point.x, 0, width)),
                'y': min(max(point.y, 0, height)),
            } for point in quad
        ]

    async def hover(self) -> None:
        """Move mouse over to center of this element.

        If needed, this method scrolls element into view. If this element is
        detached from DOM tree, the method raises an ``ElementHandleError``.
        """
        await self._scrollIntoViewIfNeeded()
        obj = await self._clickablePoint()
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
        await self._scrollIntoViewIfNeeded()
        obj = await self._clickablePoint()
        x = obj.get('x', 0)
        y = obj.get('y', 0)
        options = merge_dict(options, kwargs)
        await self._page.mouse.click(x, y, options)

    async def select(self, values: List[str]) -> List[str]:
        return await self.evaluate(
            """(element, values) => {
              if (element.nodeName.toLowerCase() !== 'select')
                throw new Error('Element is not a <select> element.');
        
              const options = Array.from(element.options);
              element.value = undefined;
              for (const option of options) {
                option.selected = values.includes(option.value);
                if (option.selected && !element.multiple)
                  break;
              }
              element.dispatchEvent(new Event('input', { bubbles: true }));
              element.dispatchEvent(new Event('change', { bubbles: true }));
              return options.filter(option => option.selected).map(option => option.value);
            }
            """,
            values
        )

    async def uploadFile(self, *filePaths: str) -> dict:
        """Upload files."""
        # TODO port this
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
        await self._scrollIntoViewIfNeeded()
        center = await self._clickablePoint()
        x = center.get('x', 0)
        y = center.get('y', 0)
        await self._page.touchscreen.tap(x, y)

    async def focus(self) -> None:
        """Focus on this element."""
        await self.executionContext.evaluate(
            'element => element.focus()', self)

    async def type(self, text: str, options: Dict = None, **kwargs) -> None:
        """Focus the element and then type text.

        Details see :meth:`pyppeteer.input.Keyboard.type` method.
        """
        options = merge_dict(options, kwargs)
        await self.focus()
        await self._page.keyboard.type(text, options)

    async def press(self, key: str, options: Dict = None, **kwargs) -> None:
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
        result = await self._getBoxModel()

        if not result:
            return None

        quad = result['model']['border']
        x = min(quad[0], quad[2], quad[4], quad[6])
        y = min(quad[1], quad[3], quad[5], quad[7])
        width = max(quad[0], quad[2], quad[4], quad[6]) - x
        height = max(quad[1], quad[3], quad[5], quad[7]) - y
        return {'x': x, 'y': y, 'width': width, 'height': height}

    async def boxModel(self) -> Optional[Dict]:
        """Return boxes of element.

        Return ``None`` if element is not visible. Boxes are represented as an
        list of points; each Point is a dictionary ``{x, y}``. Box points are
        sorted clock-wise.

        Returned value is a dictionary with the following fields:

        * ``content`` (List[Dict]): Content box.
        * ``padding`` (List[Dict]): Padding box.
        * ``border`` (List[Dict]): Border box.
        * ``margin`` (List[Dict]): Margin box.
        * ``width`` (int): Element's width.
        * ``height`` (int): Element's height.
        """
        result = await self._getBoxModel()

        if not result:
            return None

        model = result.get('model', {})
        return {
            'content': self._fromProtocolQuad(model.get('content')),
            'padding': self._fromProtocolQuad(model.get('padding')),
            'border': self._fromProtocolQuad(model.get('border')),
            'margin': self._fromProtocolQuad(model.get('margin')),
            'width': model.get('width'),
            'height': model.get('height'),
        }

    async def screenshot(self, options: Dict = None, **kwargs: Any) -> bytes:
        """Take a screenshot of this element.

        If the element is detached from DOM, this method raises an
        ``ElementHandleError``.

        Available options are same as :meth:`pyppeteer.page.Page.screenshot`.
        """
        # TODO review this
        options = merge_dict(options, kwargs)

        needsViewportReset = False
        boundingBox = await self.boundingBox()
        if not boundingBox:
            raise ElementHandleError(
                'Node is either not visible or not an HTMLElement')

        original_viewport = copy.deepcopy(self._page.viewport)

        if (boundingBox['width'] > original_viewport['width'] or
                boundingBox['height'] > original_viewport['height']):
            newViewport = {
                'width': max(
                    original_viewport['width'],
                    math.ceil(boundingBox['width'])
                ),
                'height': max(
                    original_viewport['height'],
                    math.ceil(boundingBox['height'])
                ),
            }
            new_viewport = copy.deepcopy(original_viewport)
            new_viewport.update(newViewport)
            await self._page.setViewport(new_viewport)
            needsViewportReset = True

        await self._scrollIntoViewIfNeeded()
        boundingBox = await self.boundingBox()
        if not boundingBox:
            raise ElementHandleError(
                'Node is either not visible or not an HTMLElement')

        _obj = await self._client.send('Page.getLayoutMetrics')
        pageX = _obj['layoutViewport']['pageX']
        pageY = _obj['layoutViewport']['pageY']

        clip = {}
        clip.update(boundingBox)
        clip['x'] = clip['x'] + pageX
        clip['y'] = clip['y'] + pageY
        opt = {'clip': clip}
        opt.update(options)
        imageData = await self._page.screenshot(opt)

        if needsViewportReset:
            await self._page.setViewport(original_viewport)

        return imageData

    async def querySelector(self, selector: str) -> Optional['ElementHandle']:
        """Return first element which matches ``selector`` under this element.

        If no element matches the ``selector``, returns ``None``.
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

    async def querySelectorEval(self, selector: str, pageFunction: str,
                                *args: Any) -> Any:
        """Run ``Page.querySelectorEval`` within the element.

        This method runs ``document.querySelector`` within the element and
        passes it as the first argument to ``pageFunction``. If there is no
        element matching ``selector``, the method raises
        ``ElementHandleError``.

        If ``pageFunction`` returns a promise, then wait for the promise to
        resolve and return its value.

        ``ElementHandle.Jeval`` is a shortcut of this method.

        Example:

        .. code:: python

            tweetHandle = await page.querySelector('.tweet')
            assert (await tweetHandle.querySelectorEval('.like', 'node => node.innerText')) == 100
            assert (await tweetHandle.Jeval('.retweets', 'node => node.innerText')) == 10
        """  # noqa: E501
        elementHandle = await self.querySelector(selector)
        if not elementHandle:
            raise ElementHandleError(
                f'Error: failed to find element matching selector "{selector}"'
            )
        result = await self.executionContext.evaluate(
            pageFunction, elementHandle, *args)
        await elementHandle.dispose()
        return result

    async def querySelectorAllEval(self, selector: str, pageFunction: str,
                                   *args: Any) -> Any:
        """Run ``Page.querySelectorAllEval`` within the element.

        This method runs ``Array.from(document.querySelectorAll)`` within the
        element and passes it as the first argument to ``pageFunction``. If
        there is no element matching ``selector``, the method raises
        ``ElementHandleError``.

        If ``pageFunction`` returns a promise, then wait for the promise to
        resolve and return its value.

        Example:

        .. code:: html

            <div class="feed">
                <div class="tweet">Hello!</div>
                <div class="tweet">Hi!</div>
            </div>

        .. code:: python

            feedHandle = await page.J('.feed')
            assert (await feedHandle.JJeval('.tweet', '(nodes => nodes.map(n => n.innerText))')) == ['Hello!', 'Hi!']
        """  # noqa: E501
        arrayHandle = await self.executionContext.evaluateHandle(
            '(element, selector) => Array.from(element.querySelectorAll(selector))',  # noqa: E501
            self, selector
        )
        result = await self.executionContext.evaluate(
            pageFunction, arrayHandle, *args)
        await arrayHandle.dispose()
        return result

    #: alias to :meth:`querySelector`
    J = querySelector
    #: alias to :meth:`querySelectorAll`
    JJ = querySelectorAll
    #: alias to :meth:`querySelectorEval`
    Jeval = querySelectorEval
    #: alias to :meth:`querySelectorAllEval`
    JJeval = querySelectorAllEval

    async def xpath(self, expression: str) -> List['ElementHandle']:
        """Evaluate the XPath expression relative to this elementHandle.

        If there are no such elements, return an empty list.

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

    async def isIntersectingViewport(self) -> bool:
        """Return ``True`` if the element is visible in the viewport."""
        return await self.executionContext.evaluate('''async element => {
            const visibleRatio = await new Promise(resolve => {
                const observer = new IntersectionObserver(entries => {
                    resolve(entries[0].intersectionRatio);
                    observer.disconnect();
                });
                observer.observe(element);
            });
            return visibleRatio > 0;
        }''', self)


def computeQuadArea(quad: List[Dict]) -> float:
    area = 0
    for i, _ in enumerate(quad):
        p1 = quad[i]
        p2 = quad[(i + 1) % len(quad)]
        area += (p1['x'] * p2['y'] - p2['x'] * p1['y']) / 2
    return area
