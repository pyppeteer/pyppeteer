#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Frame Manager module."""

import asyncio
from collections import OrderedDict
import re
from types import SimpleNamespace
from typing import Any, Awaitable, Dict, List, Optional, Union, TYPE_CHECKING

from pyee import EventEmitter

# from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.element_handle import ElementHandle
from pyppeteer.execution_context import ExecutionContext, JSHandle
from pyppeteer.errors import ElementHandleError, PageError, TimeoutError
from pyppeteer.util import merge_dict

if TYPE_CHECKING:
    from typing import Set  # noqa: F401
    # from pyppeteer.page import Page  # noqa: F401


class FrameManager(EventEmitter):
    """FrameManager class."""

    Events = SimpleNamespace(
        FrameAttached='frameattached',
        FrameNavigated='framenavigated',
        FrameDetached='framedetached',
        LifecycleEvent='lifecycleevent',
    )

    def __init__(self, client: Session, frameTree: Dict, page: Any) -> None:
        """Make new frame manager."""
        super().__init__()
        self._client = client
        self._page = page
        self._frames: OrderedDict[str, Frame] = OrderedDict()
        self._mainFrame: Optional[Frame] = None
        self._contextIdToContext: Dict[str, ExecutionContext] = dict()

        client.on('Page.frameAttached',
                  lambda event: self._onFrameAttached(
                      event.get('frameId', ''), event.get('parentFrameId', ''))
                  )
        client.on('Page.frameNavigated',
                  lambda event: self._onFrameNavigated(event.get('frame')))
        client.on('Page.frameDetached',
                  lambda event: self._onFrameDetached(event.get('frameId')))
        client.on('Runtime.executionContextCreated',
                  lambda event: self._onExecutionContextCreated(
                      event.get('context')))
        client.on('Page.lifecycleEvent',
                  lambda event: self._onLifecycleEvent(event))

        self._handleFrameTree(frameTree)

    def _onLifecycleEvent(self, event: Dict) -> None:
        frame = self._frames.get(event['frameId'])
        if not frame:
            return
        frame._onLifecycleEvent(event['loaderId'], event['name'])
        self.emit(FrameManager.Events.LifecycleEvent, frame)

    def _handleFrameTree(self, frameTree: Dict) -> None:
        frame = frameTree['frame']
        if 'parentId' in frame:
            self._onFrameAttached(
                frame['id'],
                frame['parentId'],
            )
        self._onFrameNavigated(frame)
        if 'childFrames' not in frameTree:
            return
        for child in frameTree['childFrames']:
            self._handleFrameTree(child)

    @property
    def mainFrame(self) -> Optional['Frame']:
        """Retrun main frame."""
        return self._mainFrame

    def frames(self) -> List['Frame']:
        """Retrun all frames."""
        return list(self._frames.values())

    def _onFrameAttached(self, frameId: str, parentFrameId: str) -> None:
        if frameId in self._frames:
            return
        parentFrame = self._frames.get(parentFrameId)
        frame = Frame(self._client, self._page, parentFrame, frameId)
        self._frames[frameId] = frame
        self.emit(FrameManager.Events.FrameAttached, frame)

    def _onFrameNavigated(self, framePayload: dict) -> None:
        isMainFrame = not framePayload.get('parentId')
        if isMainFrame:
            frame = self._mainFrame
        else:
            frame = self._frames.get(framePayload.get('id', ''))
        if not (isMainFrame or frame):
            raise PageError('We either navigate top level or have old version '
                            'of the navigated frame')

        # Detach all child frames first.
        if frame:
            for child in frame.childFrames:
                self._removeFramesRecursively(child)

        # Update or create main frame.
        _id = framePayload.get('id', '')
        if isMainFrame:
            if frame:
                # Update frame id to retain frame identity on cross-process navigation.  # noqa: E501
                self._frames.pop(frame._id, None)
                frame._id = _id
            else:
                # Initial main frame navigation.
                frame = Frame(self._client, self._page, None, _id)
            self._frames[_id] = frame
            self._mainFrame = frame

        # Update frame payload.
        frame._navigated(framePayload)  # type: ignore
        self.emit(FrameManager.Events.FrameNavigated, frame)

    def _onFrameDetached(self, frameId: str) -> None:
        frame = self._frames.get(frameId)
        if frame:
            self._removeFramesRecursively(frame)

    def _onExecutionContextCreated(self, contextPayload: Dict) -> None:
        context = ExecutionContext(
            self._client,
            contextPayload['id'],
            lambda obj: self.createJSHandle(contextPayload['id'], obj),
        )
        self._contextIdToContext[contextPayload['id']] = context

        auxData = contextPayload.get('auxData')
        frameId = (auxData.get('frameId')
                   if auxData and auxData.get('isDefault')
                   else None)
        frame = self._frames.get(frameId)
        if not frame:
            return
        frame._context = context
        for waitTask in frame._waitTasks:
            asyncio.ensure_future(waitTask.rerun())

    def _onExecutionContextDestroyed(self, contextPayload: Dict) -> None:
        del self._contextIdToContext[contextPayload['id']]

    def createJSHandle(self, contextId: str, remoteObject: Dict = None
                       ) -> 'JSHandle':
        """Create JS handle associated to the context id and remote object."""
        if remoteObject is None:
            remoteObject = dict()
        context = self._contextIdToContext.get(contextId)
        if not context:
            raise ElementHandleError(f'missing context with id = {contextId}')
        if remoteObject.get('subtype') == 'node':
            return ElementHandle(context, self._client, remoteObject,
                                 self._page)
        return JSHandle(context, self._client, remoteObject)

    def _removeFramesRecursively(self, frame: 'Frame') -> None:
        for child in frame.childFrames:
            self._removeFramesRecursively(child)
        frame._detach()
        self._frames.pop(frame._id, None)
        self.emit(FrameManager.Events.FrameDetached, frame)


class Frame(object):
    """Frame class."""

    def __init__(self, client: Session, page: Any,
                 parentFrame: Optional['Frame'], frameId: str) -> None:
        """Make new frame."""
        self._client = client
        self._page = page
        self._parentFrame = parentFrame
        self._url = ''
        self._detached = False
        self._id = frameId
        self._context: Optional[ExecutionContext] = None
        self._waitTasks: Set[WaitTask] = set()  # maybe list
        self._loaderId = ''
        self._lifecycleEvents: Set[str] = set()
        self._childFrames: Set[Frame] = set()  # maybe list
        if self._parentFrame:
            self._parentFrame._childFrames.add(self)

    @property
    def executionContext(self) -> Optional[ExecutionContext]:
        """Return execution context of this frame."""
        return self._context

    async def evaluate(self, pageFunction: str, *args: Any,
                       force_expr: bool = False) -> Any:
        """Evaluate pageFunction on this frame."""
        if self._context is None:
            raise ElementHandleError('ExecutionContext is None.')
        return await self._context.evaluate(
            pageFunction, *args, force_expr=force_expr)

    async def querySelector(self, selector: str) -> Optional[ElementHandle]:
        """Get element which matches `selector` string.

        If `selector` matches multiple elements, return first-matched element.
        """
        if self._context is None:
            raise ElementHandleError('ExecutionContext is None.')
        handle = await self._context.evaluateHandle(
            'selector => document.querySelector(selector)', selector)
        element = handle.asElement()
        if element:
            return element
        await handle.dispose()
        return None

    async def querySelectorEval(self, selector: str, pageFunction: str,
                                *args: Any) -> Optional[Any]:
        """Execute function on element which matches selector."""
        elementHandle = await self.querySelector(selector)
        if elementHandle is None:
            raise PageError(
                f'Error: failed to find element matching selector "{selector}"'
            )
        result = await self.evaluate(pageFunction, elementHandle, *args)
        await elementHandle.dispose()
        return result

    async def querySelectorAllEval(self, selector: str, pageFunction: str,
                                   *args: Any) -> Optional[Dict]:
        """Execute function on all elements which matches selector."""
        if self._context is None:
            raise ElementHandleError('ExecutionContext is None.')
        arrayHandle = await self._context.evaluateHandle(
            'selector => Array.from(document.querySelectorAll(selector))',
            selector,
        )
        result = await self.evaluate(pageFunction, arrayHandle, *args)
        await arrayHandle.dispose()
        return result

    async def querySelectorAll(self, selector: str) -> List[ElementHandle]:
        """Get all elelments which matches `selector`."""
        if self._context is None:
            raise ElementHandleError('ExecutionContext is None.')
        arrayHandle = await self._context.evaluateHandle(
            'selector => document.querySelectorAll(selector)',
            selector,
        )
        properties = await arrayHandle.getProperties()
        await arrayHandle.dispose()
        result = []
        for prop in properties.values():
            elementHandle = prop.asElement()
            if elementHandle:
                result.append(elementHandle)
        return result

    #: Alias to querySelector
    J = querySelector
    Jeval = querySelectorEval
    JJ = querySelectorAll
    JJeval = querySelectorAllEval

    @property
    def name(self) -> str:
        """Get frame name."""
        return self.__dict__.get('_name', '')

    @property
    def url(self) -> str:
        """Get url."""
        return self._url

    @property
    def parentFrame(self) -> Optional['Frame']:
        """Get parent frame."""
        return self._parentFrame

    @property
    def childFrames(self) -> List['Frame']:
        """Get child frames."""
        return list(self._childFrames)

    @property
    def isDetached(self) -> bool:
        """Check if this frame is detached."""
        return self._detached

    async def injectFile(self, filePath: str) -> str:
        """Inject file to the frame."""
        # to be changed to async func
        with open(filePath) as f:
            contents = f.read()
        contents += '/* # sourceURL= {} */'.format(filePath.replace('\n', ''))
        return await self.evaluate(contents)

    async def addScriptTag(self, options: Dict) -> ElementHandle:
        """Add script tag to this frame."""
        if self._context is None:
            raise ElementHandleError('ExecutionContext is None.')

        addScriptUrl = '''
        async function addScriptUrl(url) {
            const script = document.createElement('script');
            script.src = url;
            document.head.appendChild(script);
            await new Promise((res, rej) => {
                script.onload = res;
                script.onerror = rej;
            });
            return script;
        }'''

        addScriptContent = '''
        function addScriptContent(content) {
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.text = content;
            document.head.appendChild(script);
            return script;
        }'''

        if isinstance(options.get('url'), str):
            return await self._context.evaluateHandle(  # type: ignore
                addScriptUrl, options['url'])

        if isinstance(options.get('path'), str):
            with open(options['path']) as f:
                contents = f.read()
            contents = contents + '//# sourceURL={}'.format(
                re.sub(options['path'], '\n', ''))
            return await self._context.evaluateHandle(  # type: ignore
                addScriptContent, contents)

        if isinstance(options.get('content'), str):
            return await self._context.evaluateHandle(  # type: ignore
                addScriptContent, options['content'])

        raise ValueError(
            'Provide an object with a `url`, `path` or `content` property')

    async def addStyleTag(self, options: Dict) -> ElementHandle:
        """Add style tag to this frame."""
        addStyleUrl = '''
        async function (url) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            document.head.appendChild(link);
            await new Promise((res, rej) => {
                link.onload = res;
                link.onerror = rej;
            });
            return link;
        }'''

        addStyleContent = '''
        function (content) {
            const style = document.createElement('style');
            style.type = 'text/css';
            style.appendChild(document.createTextNode(content));
            document.head.appendChild(style);
            return style;
        }'''

        if isinstance(options.get('url'), str):
            return await self._context.evaluateHandle(  # type: ignore
                addStyleUrl, options['url'])

        if isinstance(options.get('path'), str):
            with open(options['path']) as f:
                contents = f.read()
            contents = contents + '/*# sourceURL={}*/'.format(re.sub(options['path'], '\n', ''))  # noqa: E501
            return await self._context.evaluateHandle(  # type: ignore
                addStyleContent, contents)

        if isinstance(options.get('content'), str):
            return await self._context.evaluateHandle(  # type: ignore
                addStyleContent, options['content'])

        raise ValueError(
            'Provide an object with a `url`, `path` or `content` property')

    async def select(self, selector: str, *values: str) -> List[str]:
        """Select options and return selected values."""
        return await self.querySelectorEval(  # type: ignore
            selector, '''
(element, values) => {
    if (element.nodeName.toLowerCase() !== 'select')
        throw new Error('Element is not a <select> element.');

    const options = Array.from(element.options);
    element.value = undefined;
    for (const option of options)
        option.selected = values.includes(option.value);

    element.dispatchEvent(new Event('input', { 'bubbles': true }));
    element.dispatchEvent(new Event('change', { 'bubbles': true }));
    return options.filter(option => option.selected).map(options => options.value)
}
        ''', values)  # noqa: E501

    def waitFor(self, selectorOrFunctionOrTimeout: Union[str, int, float],
                options: dict = None, *args: Any, **kwargs: Any) -> Awaitable:
        """Wait until `selectorOrFunctionOrTimeout`."""
        options = merge_dict(options, kwargs)
        if isinstance(selectorOrFunctionOrTimeout, (int, float)):
            fut: Awaitable[None] = asyncio.ensure_future(
                asyncio.sleep(selectorOrFunctionOrTimeout))
            return fut
        if not isinstance(selectorOrFunctionOrTimeout, str):
            fut = asyncio.get_event_loop().create_future()
            fut.set_exception(TypeError(
                'Unsupported target type: ' +
                str(type(selectorOrFunctionOrTimeout))
            ))
            return fut
        if ('=>' in selectorOrFunctionOrTimeout or
                selectorOrFunctionOrTimeout.strip().startswith('function')):
            return self.waitForFunction(
                selectorOrFunctionOrTimeout, options, *args)
        return self.waitForSelector(selectorOrFunctionOrTimeout, options)

    def waitForSelector(self, selector: str, options: dict = None,
                        **kwargs: Any) -> Awaitable:
        """Wait for selector matches element."""
        options = merge_dict(options, kwargs)
        waitForVisible = bool(options.get('visible'))
        waitForHidden = bool(options.get('hidden'))
        pageFunction = '''
(selector, waitForVisible, waitForHidden) => {
    const node = document.querySelector(selector);
    if (!node)
        return waitForHidden;
    if (!waitForVisible && !waitForHidden)
        return true;
    const style = window.getComputedStyle(node);
    const isVisible = style && style.visibility !== 'hidden' && hasVisibleBoundingBox();
    return (waitForVisible === isVisible || waitForHidden === !isVisible);

    function hasVisibleBoundingBox() {
        const rect = node.getBoundingClientRect();
        return !!(rect.top || rect.bottom || rect.width || rect.height);
    }
}
        '''  # noqa: E501
        return self.waitForFunction(
            pageFunction, options, selector, waitForVisible, waitForHidden)

    def waitForFunction(self, pageFunction: str, options: dict = None,
                        *args: Any, **kwargs: Any) -> Awaitable:
        """Wait for js function return true."""
        options = merge_dict(options, kwargs)
        timeout = options.get('timeout',  30000)  # msec
        interval = options.get('interval', 0)  # msec
        return WaitTask(self, pageFunction, timeout, *args, interval=interval)

    async def title(self) -> str:
        """Get title of the frame."""
        return await self.evaluate('() => document.title')

    def _navigated(self, framePayload: dict) -> None:
        self._name = framePayload.get('name', '')
        self._url = framePayload.get('url', '')

    def _onLifecycleEvent(self, loaderId: str, name: str) -> None:
        if name == 'init':
            self._loaderId = loaderId
            self._lifecycleEvents.clear()
        else:
            self._lifecycleEvents.add(name)

    def _detach(self) -> None:
        for waitTask in self._waitTasks:
            waitTask.terminate(
                PageError('waitForSelector failed: frame got detached.'))
        self._detached = True
        if self._parentFrame:
            self._parentFrame._childFrames.remove(self)
        self._parentFrame = None


class WaitTask(asyncio.Future):
    """WaitTask class."""

    def __init__(self, frame: Frame, expr: str, timeout: float,
                 *args: Any, interval: float = 0) -> None:
        """Make new wait task.

        :arg float timeout: msec to wait for task [default 30_000 [msec]].
        :arg float interval: msec to poll for task [default timeout / 1000].
        """
        super().__init__()
        self.__frame: Frame = frame
        self.expr = expr
        self.args = args
        self.__timeout = timeout / 1000  # sec
        self.__interval = interval / 1000 or self.__timeout / 100  # sec
        self.__runCount: int = 0
        self.__terminated = False
        self.__done = False
        frame._waitTasks.add(self)
        # Since page navigation requires us to re-install the pageScript,
        # we should track timeout on our end.
        self.__loop = asyncio.get_event_loop()
        self.__timeoutTimer = self.__loop.call_later(
            self.__timeout,
            lambda: self.terminate(
                TimeoutError(f'waiting failed: timeout {timeout}ms exceeded')
            )
        )
        asyncio.ensure_future(self.rerun(True))

    def terminate(self, error: Exception) -> None:
        """Terminate task by error."""
        self.__terminated = True
        self.set_exception(error)
        self.__cleanup()

    async def rerun(self, internal: bool = False) -> None:  # noqa: C901
        """Re-run the task."""
        if self.__done:
            return
        self.__runCount += 1
        runCount = self.__runCount
        success = False
        error = None
        try:
            success = bool(await self.__frame.evaluate(self.expr, *self.args))
        except Exception as e:
            error = e

        if self.__terminated or runCount != self.__runCount:
            return

        # Ignore timeouts in pageScript - we track timeouts ourselves.
        if not success and not error:
            if internal:
                self.__loop.call_later(
                    self.__interval,
                    lambda: asyncio.ensure_future(self.rerun(True)),
                )
            return

        # When the page is navigated, the promise is rejected.
        # We will try again in the new execution context.
        if error:
            error_msg = str(error)
            if 'Execution context was destroyed' in error_msg:
                return

        if error:
            self.set_exception(error)
        else:
            self.set_result(None)
        self.__cleanup()

    def __cleanup(self) -> None:
        self.__timeoutTimer.cancel()
        self.__frame._waitTasks.remove(self)
        self._runningTask = None
        self.__done = True
