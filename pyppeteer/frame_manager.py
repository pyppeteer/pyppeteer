#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Frame Manager module."""

import asyncio
import re
import logging
from types import SimpleNamespace
from typing import Any, Awaitable, Dict, List, Optional, Set, Union

from pyee import EventEmitter

from pyppeteer import helper
from pyppeteer.domworld import DOMWorld
from pyppeteer.events import Events
from pyppeteer.jshandle import JSHandle
from pyppeteer.connection import CDPSession
from pyppeteer.element_handle import ElementHandle
from pyppeteer.errors import BrowserError
from pyppeteer.execution_context import ExecutionContext
from pyppeteer.errors import ElementHandleError, PageError
from pyppeteer.lifecycle_watcher import LifecycleWatcher
from pyppeteer.network_manager import NetworkManager
from pyppeteer.timeout_settings import TimeoutSettings
from pyppeteer.util import merge_dict

logger = logging.getLogger(__name__)

UTILITY_WORLD_NAME = '__puppeteer_utility_world__'
EVALUATION_SCRIPT_URL = '__puppeteer_evaluation_script__'
SOURCE_URL_REGEX = re.compile(
    r'^[ \t]*//[@#] sourceURL=\s*(\S*?)\s*$',
    re.MULTILINE,
)


class FrameManager(EventEmitter):
    """FrameManager class."""

    def __init__(
            self,
            client: CDPSession,
            page: Any,
            ignoreHTTPSErrors: bool,
            timeoutSettings: 'TimeoutSettings'
    ) -> None:
        """Make new frame manager."""
        super().__init__()
        self._client = client
        self._page = page
        self._networkManager = NetworkManager(client, ignoreHTTPSErrors, self)
        self._timeoutSettings = timeoutSettings
        self._frames: OrderedDict[str, Frame] = OrderedDict()
        self._contextIdToContext: Dict[int, ExecutionContext] = {}
        self._isolatedWorlds: Set[str] = set()

        client.on(
            'Page.frameAttached',
            lambda event: self._onFrameAttached(
                event.get('frameId', ''), event.get('parentFrameId', ''))
        )
        client.on(
            'Page.frameNavigated',
            lambda event: self._onFrameNavigated(event.get('frame'))
        )
        client.on(
            'Page.navigatedWithinDocument',
            lambda event: self._onFrameNavigatedWithinDocument(
                event.get('frameId'), event.get('url'))
        )
        client.on(
            'Page.frameDetached',
            lambda event: self._onFrameDetached(event.get('frameId'))
        )
        client.on(
            'Page.frameStoppedLoading',
            lambda event: self._onFrameStoppedLoading(event.get('frameId'))
        )
        client.on(
            'Runtime.executionContextCreated',
            lambda event: self._onExecutionContextCreated(event.get('context'))
        )
        client.on(
            'Runtime.executionContextDestroyed',
            lambda event: self._onExecutionContextDestroyed(
                event.get('executionContextId'))
        )
        client.on(
            'Runtime.executionContextsCleared',
            lambda event: self._onExecutionContextsCleared()
        )
        client.on(
            'Page.lifecycleEvent',
            lambda event: self._onLifecycleEvent(event)
        )

    async def initiliaze(self):
        frameTree = await asyncio.gather(
            self._client.send('Page.enable'),
            self._client.send('Page.getFrameTree'),
        )
        self._handleFrameTree(frameTree)

        async def runtime_enabled():
            await self._client.send('Runtime.enable', {})
            await self._ensureIsolatedWorld(UTILITY_WORLD_NAME)

        await asyncio.gather(
            self._client.send(
                'Page.setLifecycleEventsEnabled',
                {'enabled': True}
            ),
            await self._networkManager.initialize()
        )

    @property
    def networkManager(self):
        return self._networkManager

    async def navigateFrame(
            self,
            frame: 'Frame',
            url: str,
            referer: str = None,
            timeout: int = None,
            waitUntil: Union[str, List[str]] = None,
    ):
        ensureNewDocumentNavigation = False

        async def navigate(url: str, referer: str, frameId: str):
            try:
                response = await self._client.send(
                    'Page.navigate',
                    {
                        'url': url,
                        'referer': referer,
                        'frameId': frameId,
                    }
                )
                # todo local functions in python cannot modify outer namespaces
                ensureNewDocumentNavigation = bool(response.get('loaderId'))
                if response.get('errorText'):
                    raise BrowserError(f'{response["errorText"]} at {url}')
            except Exception as e:
                return e

        if referer is None:
            referer = self._networkManager.extraHTTPHeaders().get('referer', '')
        if waitUntil is None:
            waitUntil = ['load']
        if timeout is None:
            timeout = self._timeoutSettings.navigationTimeout

        watcher = LifecycleWatcher(self, frame, waitUntil, timeout)
        error = await asyncio.wait([
            navigate(url, referer, frame._id),
            watcher.timeoutOrTerminationPromise()
        ], return_when=asyncio.FIRST_COMPLETED)
        if not error:
            if ensureNewDocumentNavigation:
                nav_promise = watcher.newDocumentNavigationPromise()
            else:
                nav_promise = watcher.sameDocumentNavigationPromise()
            error = await asyncio.wait([
                watcher.timeoutOrTerminationPromise(),
                nav_promise,
            ], return_when=asyncio.FIRST_COMPLETED)
        watcher.dispose()
        if error:
            raise error
        return watcher.navigationResponse()

    async def waitForFrameNavigation(
            self,
            frame: 'Frame',
            waitUntil: Union[str, List[str]] = None,
            timeout: int = None
    ):
        if not waitUntil:
            waitUntil = ['load']
        if not timeout:
            timeout = self._timeoutSettings.navigationTimeout
        watcher = LifecycleWatcher(self, frame, waitUntil, timeout)
        error = asyncio.wait([
            watcher.timeoutOrTerminationPromise(),
            watcher.sameDocumentNavigationPromise(),
            watcher.newDocumentNavigationPromise(),
        ], return_when=asyncio.FIRST_COMPLETED)
        watcher.dispose()
        if error:
            raise error
        return watcher.navigationResponse()

    def _onLifecycleEvent(self, event: Dict) -> None:
        frame = self._frames.get(event['frameId'])
        if not frame:
            return
        frame._onLifecycleEvent(event['loaderId'], event['name'])
        self.emit(Events.FrameManager.LifecycleEvent, frame)

    def _onFrameStoppedLoading(self, frameId: str) -> None:
        frame = self._frames.get(frameId)
        if not frame:
            return
        frame._onLoadingStopped()
        self.emit(Events.FrameManager.LifecycleEvent, frame)

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
    def page(self):
        return self._page

    @property
    def mainFrame(self) -> Optional['Frame']:
        """Return main frame."""
        return self._mainFrame

    def frames(self) -> List['Frame']:
        """Return all frames."""
        return list(self._frames.values())

    def frame(self, frameId: str) -> Optional['Frame']:
        """Return :class:`Frame` of ``frameId``."""
        return self._frames.get(frameId)

    def _onFrameAttached(self, frameId: str, parentFrameId: str) -> None:
        if frameId in self._frames:
            return
        parentFrame = self._frames.get(parentFrameId)
        frame = Frame(self._client, parentFrame, frameId)
        self._frames[frameId] = frame
        self.emit(Events.FrameManager.FrameAttached, frame)

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
                frame = Frame(self._client, None, _id)
            self._frames[_id] = frame
            self._mainFrame = frame

        # Update frame payload.
        frame._navigated(framePayload)  # type: ignore
        self.emit(Events.FrameManager.FrameNavigated, frame)

    async def _ensureIsolatedWorld(self, name: str):
        if name in self._isolatedWorlds:
            return
        self._isolatedWorlds.add(name)
        await self._client.send(
            'Page.addScriptToEvaluateOnNewDocument',
            {
                'source': f'//# sourceURL={EVALUATION_SCRIPT_URL}',
                'worldName': name,
            }
        )
        # todo wrap in debugerror?
        await asyncio.gather(
            *[self._client.send(
                'Page.createIsolatedWorld',
                {
                    'frameId': frame._id,
                    'grantUniversalAccess': True,
                    'worldName': name,
                }
            ) for frame in self.frames()]
        )

    def _onFrameNavigatedWithinDocument(self, frameId: str, url: str) -> None:
        frame = self._frames.get(frameId)
        if not frame:
            return
        frame._navigatedWithinDocument(url)
        self.emit(Events.FrameManager.FrameNavigatedWithinDocument, frame)
        self.emit(Events.FrameManager.FrameNavigated, frame)

    def _onFrameDetached(self, frameId: str) -> None:
        frame = self._frames.get(frameId)
        if frame:
            self._removeFramesRecursively(frame)

    def _onExecutionContextCreated(self, contextPayload: Dict) -> None:
        auxData = contextPayload.get('auxData')
        frameId = auxData.get('frameId')
        frame = self._frames.get(frameId)
        world = None
        if frame:
            if auxData and not auxData['isDefault']:
                world = frame._mainWorld
            elif contextPayload.get('name') == UTILITY_WORLD_NAME \
                    and not frame._secondaryWorld._hasContext():
                # In case of multiple sessions to the same target, there's a race between
                # connections so we might end up creating multiple isolated worlds.
                # We can use either.
                world = frame._secondaryWorld
        if auxData and auxData.get('type') == 'isolated':
            self._isolatedWorlds.add(contextPayload['name'])

        context = ExecutionContext(
            self._client,
            contextPayload,
            world
        )
        if world:
            world._setContext(context)
        self._contextIdToContext[contextPayload['id']] = context

    def _onExecutionContextDestroyed(self, executionContextId: str) -> None:
        context = self._contextIdToContext.get(executionContextId)
        if not context:
            return
        del self._contextIdToContext[executionContextId]
        if context._world:
            context._world._setContext(None)

    def _onExecutionContextsCleared(self) -> None:
        for context in self._contextIdToContext.values():
            if context._world:
                context._world._setContext(None)
        self._contextIdToContext.clear()

    def executionContextById(self, contextId: str) -> ExecutionContext:
        """Get stored ``ExecutionContext`` by ``id``."""
        context = self._contextIdToContext.get(contextId)
        if not context:
            raise ElementHandleError(
                f'INTERNAL ERROR: missing context with id = {contextId}'
            )
        return context

    def _removeFramesRecursively(self, frame: 'Frame') -> None:
        for child in frame.childFrames:
            self._removeFramesRecursively(child)
        frame._detach()
        self._frames.pop(frame._id, None)
        self.emit(Events.FrameManager.FrameDetached, frame)


class Frame(object):
    """Frame class.

    Frame objects can be obtained via :attr:`pyppeteer.page.Page.mainFrame`.
    """

    def __init__(
            self,
            frameManager: FrameManager,
            client: CDPSession,
            parentFrame: Optional['Frame'],
            frameId: str
    ) -> None:
        self._frameManager = frameManager
        self._client = client
        self._parentFrame = parentFrame
        self._url = ''
        self._id = frameId
        self._detached = False

        self._loaderId = ''
        self._lifecycleEvents: Set[str] = set()
        self._mainWorld = DOMWorld(frameManager, self, FrameManager._timeoutSettings)
        self._secondaryWorld = DOMWorld(frameManager, self, FrameManager._timeoutSettings)
        self._childFrames: Set[Frame] = set()  # maybe list
        if self._parentFrame:
            self._parentFrame._childFrames.add(self)

        # todo remove this?
        self._documentPromise: Optional[ElementHandle] = None
        self._contextResolveCallback = lambda _: None
        self._setDefaultContext(None)

        self._waitTasks: Set[WaitTask] = set()  # maybe list
        if self._parentFrame:
            self._parentFrame._childFrames.add(self)

    def _addExecutionContext(self, context: ExecutionContext) -> None:
        if context._isDefault:
            self._setDefaultContext(context)

    def _removeExecutionContext(self, context: ExecutionContext) -> None:
        if context._isDefault:
            self._setDefaultContext(None)

    def _setDefaultContext(self, context: Optional[ExecutionContext]) -> None:
        if context is not None:
            self._contextResolveCallback(context)  # type: ignore
            self._contextResolveCallback = lambda _: None
            for waitTask in self._waitTasks:
                self._client._loop.create_task(waitTask.rerun())
        else:
            self._documentPromise = None
            self._contextPromise = self._client._loop.create_future()
            self._contextResolveCallback = (
                lambda _context: self._contextPromise.set_result(_context)
            )

    async def goto(self, url, **kwargs):
        return await self._frameManager.navigateFrame(self, url, **kwargs)

    async def waitForNavigation(self, **kwargs):
        return await self._frameManager.waitForFrameNavigation(self, **kwargs)

    async def executionContext(self) -> Optional[ExecutionContext]:
        """Return execution context of this frame.

        Return :class:`~pyppeteer.execution_context.ExecutionContext`
        associated to this frame.
        """
        return await self._contextPromise

    async def evaluateHandle(self, pageFunction: str, *args: Any) -> JSHandle:
        """Execute function on this frame.

        Details see :meth:`pyppeteer.page.Page.evaluateHandle`.
        """
        context = await self.executionContext()
        if context is None:
            raise PageError('this frame has no context.')
        return await context.evaluateHandle(pageFunction, *args)

    async def evaluate(self, pageFunction: str, *args: Any,
                       force_expr: bool = False) -> Any:
        """Evaluate pageFunction on this frame.

        Details see :meth:`pyppeteer.page.Page.evaluate`.
        """
        context = await self.executionContext()
        if context is None:
            raise ElementHandleError('ExecutionContext is None.')
        return await context.evaluate(
            pageFunction, *args, force_expr=force_expr)

    async def querySelector(self, selector: str) -> Optional[ElementHandle]:
        """Get element which matches `selector` string.

        Details see :meth:`pyppeteer.page.Page.querySelector`.
        """
        document = await self._document()
        value = await document.querySelector(selector)
        return value

    async def _document(self) -> ElementHandle:
        if self._documentPromise:
            return self._documentPromise
        context = await self.executionContext()
        if context is None:
            raise PageError('No context exists.')
        document = (await context.evaluateHandle('document')).asElement()
        self._documentPromise = document
        if document is None:
            raise PageError('Could not find `document`.')
        return document

    async def xpath(self, expression: str) -> List[ElementHandle]:
        """Evaluate the XPath expression.

        If there are no such elements in this frame, return an empty list.

        :arg str expression: XPath string to be evaluated.
        """
        document = await self._document()
        value = await document.xpath(expression)
        return value

    async def querySelectorEval(self, selector: str, pageFunction: str,
                                *args: Any) -> Any:
        """Execute function on element which matches selector.

        Details see :meth:`pyppeteer.page.Page.querySelectorEval`.
        """
        document = await self._document()
        return await document.querySelectorEval(selector, pageFunction, *args)

    async def querySelectorAllEval(self, selector: str, pageFunction: str,
                                   *args: Any) -> Optional[Dict]:
        """Execute function on all elements which matches selector.

        Details see :meth:`pyppeteer.page.Page.querySelectorAllEval`.
        """
        document = await self._document()
        value = await document.JJeval(selector, pageFunction, *args)
        return value

    async def querySelectorAll(self, selector: str) -> List[ElementHandle]:
        """Get all elements which matches `selector`.

        Details see :meth:`pyppeteer.page.Page.querySelectorAll`.
        """
        document = await self._document()
        value = await document.querySelectorAll(selector)
        return value

    #: Alias to :meth:`querySelector`
    J = querySelector
    #: Alias to :meth:`xpath`
    Jx = xpath
    #: Alias to :meth:`querySelectorEval`
    Jeval = querySelectorEval
    #: Alias to :meth:`querySelectorAll`
    JJ = querySelectorAll
    #: Alias to :meth:`querySelectorAllEval`
    JJeval = querySelectorAllEval

    async def content(self) -> str:
        """Get the whole HTML contents of the page."""
        return await self.evaluate('''
() => {
  let retVal = '';
  if (document.doctype)
    retVal = new XMLSerializer().serializeToString(document.doctype);
  if (document.documentElement)
    retVal += document.documentElement.outerHTML;
  return retVal;
}
        '''.strip())

    async def setContent(self, html: str) -> None:
        """Set content to this page."""
        func = '''
function(html) {
  document.open();
  document.write(html);
  document.close();
}
'''
        await self.evaluate(func, html)

    @property
    def name(self) -> str:
        """Get frame name."""
        return self.__dict__.get('_name', '')

    @property
    def url(self) -> str:
        """Get url of the frame."""
        return self._url

    @property
    def parentFrame(self) -> Optional['Frame']:
        """Get parent frame.

        If this frame is main frame or detached frame, return ``None``.
        """
        return self._parentFrame

    @property
    def childFrames(self) -> List['Frame']:
        """Get child frames."""
        return list(self._childFrames)

    def isDetached(self) -> bool:
        """Return ``True`` if this frame is detached.

        Otherwise return ``False``.
        """
        return self._detached

    async def addScriptTag(self, options: Dict) -> ElementHandle:  # noqa: C901
        """Add script tag to this frame.

        Details see :meth:`pyppeteer.page.Page.addScriptTag`.
        """
        context = await self.executionContext()
        if context is None:
            raise ElementHandleError('ExecutionContext is None.')

        addScriptUrl = '''
        async function addScriptUrl(url, type) {
            const script = document.createElement('script');
            script.src = url;
            if (type)
                script.type = type;
            const promise = new Promise((res, rej) => {
                script.onload = res;
                script.onerror = rej;
            });
            document.head.appendChild(script);
            await promise;
            return script;
        }'''

        addScriptContent = '''
        function addScriptContent(content, type = 'text/javascript') {
            const script = document.createElement('script');
            script.type = type;
            script.text = content;
            let error = null;
            script.onerror = e => error = e;
            document.head.appendChild(script);
            if (error)
                throw error;
            return script;
        }'''

        if isinstance(options.get('url'), str):
            url = options['url']
            args = [addScriptUrl, url]
            if 'type' in options:
                args.append(options['type'])
            try:
                return (await context.evaluateHandle(*args)  # type: ignore
                        ).asElement()
            except ElementHandleError as e:
                raise PageError(f'Loading script from {url} failed') from e

        if isinstance(options.get('path'), str):
            with open(options['path']) as f:
                contents = f.read()
            contents = contents + '//# sourceURL={}'.format(
                options['path'].replace('\n', ''))
            args = [addScriptContent, contents]
            if 'type' in options:
                args.append(options['type'])
            return (await context.evaluateHandle(*args)  # type: ignore
                    ).asElement()

        if isinstance(options.get('content'), str):
            args = [addScriptContent, options['content']]
            if 'type' in options:
                args.append(options['type'])
            return (await context.evaluateHandle(*args)  # type: ignore
                    ).asElement()

        raise ValueError(
            'Provide an object with a `url`, `path` or `content` property')

    async def addStyleTag(self, options: Dict) -> ElementHandle:
        """Add style tag to this frame.

        Details see :meth:`pyppeteer.page.Page.addStyleTag`.
        """
        context = await self.executionContext()
        if context is None:
            raise ElementHandleError('ExecutionContext is None.')

        addStyleUrl = '''
        async function (url) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            const promise = new Promise((res, rej) => {
                link.onload = res;
                link.onerror = rej;
            });
            document.head.appendChild(link);
            await promise;
            return link;
        }'''

        addStyleContent = '''
        async function (content) {
            const style = document.createElement('style');
            style.type = 'text/css';
            style.appendChild(document.createTextNode(content));
            const promise = new Promise((res, rej) => {
                style.onload = res;
                style.onerror = rej;
            });
            document.head.appendChild(style);
            await promise;
            return style;
        }'''

        if isinstance(options.get('url'), str):
            url = options['url']
            try:
                return (await context.evaluateHandle(  # type: ignore
                    addStyleUrl, url)).asElement()
            except ElementHandleError as e:
                raise PageError(f'Loading style from {url} failed') from e

        if isinstance(options.get('path'), str):
            with open(options['path']) as f:
                contents = f.read()
            contents = contents + '/*# sourceURL={}*/'.format(
                options['path'].replace('\n', ''))
            return (await context.evaluateHandle(  # type: ignore
                addStyleContent, contents)).asElement()

        if isinstance(options.get('content'), str):
            return (await context.evaluateHandle(  # type: ignore
                addStyleContent, options['content'])).asElement()

        raise ValueError(
            'Provide an object with a `url`, `path` or `content` property')

    async def click(self, selector: str, options: dict = None, **kwargs: Any
                    ) -> None:
        """Click element which matches ``selector``.

        Details see :meth:`pyppeteer.page.Page.click`.
        """
        options = merge_dict(options, kwargs)
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.click(options)
        await handle.dispose()

    async def focus(self, selector: str) -> None:
        """Focus element which matches ``selector``.

        Details see :meth:`pyppeteer.page.Page.focus`.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await self.evaluate('element => element.focus()', handle)
        await handle.dispose()

    async def hover(self, selector: str) -> None:
        """Mouse hover the element which matches ``selector``.

        Details see :meth:`pyppeteer.page.Page.hover`.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.hover()
        await handle.dispose()

    async def select(self, selector: str, *values: str) -> List[str]:
        """Select options and return selected values.

        Details see :meth:`pyppeteer.page.Page.select`.
        """
        for value in values:
            if not isinstance(value, str):
                raise TypeError(
                    'Values must be string. '
                    f'Found {value} of type {type(value)}'
                )
        return await self.querySelectorEval(  # type: ignore
            selector, '''
(element, values) => {
    if (element.nodeName.toLowerCase() !== 'select')
        throw new Error('Element is not a <select> element.');

    const options = Array.from(element.options);
    element.value = undefined;
    for (const option of options) {
        option.selected = values.includes(option.value);
        if (option.selected && !element.multiple)
            break;
    }

    element.dispatchEvent(new Event('input', { 'bubbles': true }));
    element.dispatchEvent(new Event('change', { 'bubbles': true }));
    return options.filter(option => option.selected).map(options => options.value)
}
        ''', values)  # noqa: E501

    async def tap(self, selector: str) -> None:
        """Tap the element which matches the ``selector``.

        Details see :meth:`pyppeteer.page.Page.tap`.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.tap()
        await handle.dispose()

    async def type(self, selector: str, text: str, options: dict = None,
                   **kwargs: Any) -> None:
        """Type ``text`` on the element which matches ``selector``.

        Details see :meth:`pyppeteer.page.Page.type`.
        """
        options = merge_dict(options, kwargs)
        handle = await self.querySelector(selector)
        if handle is None:
            raise PageError('Cannot find {} on this page'.format(selector))
        await handle.type(text, options)
        await handle.dispose()

    def waitFor(
            self,
            selectorOrFunctionOrTimeout: Union[str, int, float],
            *args: Any,
            **kwargs: Any
    ) -> Union[Awaitable, 'WaitTask']:
        """Wait until `selectorOrFunctionOrTimeout`.

        Details see :meth:`pyppeteer.page.Page.waitFor`.
        """
        xPathPattern = '//'
        if isinstance(selectorOrFunctionOrTimeout, str):
            string = selectorOrFunctionOrTimeout
            if string.startswith(xPathPattern):
                return self.waitForXPath(string, **kwargs)
            return self.waitForSelector(string, **kwargs)
        if isinstance(selectorOrFunctionOrTimeout, (int, float)):
            return self._client._loop.create_task(
                asyncio.sleep(selectorOrFunctionOrTimeout / 1000)
            )
        if helper.is_jsfunc(selectorOrFunctionOrTimeout):
            return self.waitForFunction(
                selectorOrFunctionOrTimeout, *args, **kwargs
            )
        f = self._client._loop.create_future()
        f.set_exception(BrowserError(f'Unsupported target type:'
                                     f' {type(selectorOrFunctionOrTimeout)}'))
        return f

    async def waitForSelector(
            self,
            selector: str,
            **kwargs: Any
    ) -> Optional[ElementHandle]:
        """Wait until element which matches ``selector`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForSelector`.
        """
        handle = await self._secondaryWorld.waitForSelector(selector, **kwargs)
        if not handle:
            return None
        mainExecutionContext = await self._mainWorld.executionContext()
        result = await mainExecutionContext._adoptElementHandle()
        await handle.dispose()
        return result

    def waitForXPath(
            self,
            xpath: str,
            options: dict = None,
            **kwargs: Any
    ) -> 'WaitTask':
        """Wait until element which matches ``xpath`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForXPath`.
        """
        handle = await self._secondaryWorld.waitForXpath(xpath, **kwargs)
        if not handle:
            return None
        mainExecutionContext = await self._mainWorld.executionContext()
        result = await mainExecutionContext._adoptElementHandle(handle)
        await handle.dispose()
        return result

    def waitForFunction(
            self,
            pageFunction: str,
            *args,
            **kwargs: Any
    ) -> 'WaitTask':
        """Wait until the function completes.

        Details see :meth:`pyppeteer.page.Page.waitForFunction`.
        """
        kwargs.setdefault('timeout', 30_000)
        kwargs.setdefault('polling', 'raf')
        return self._mainWorld.waitForFunction(pageFunction, *args, **kwargs)

    async def title(self):
        """Get title of the frame."""
        return await self._secondaryWorld.title()

    def _navigated(self, framePayload: dict) -> None:
        self._name = framePayload.get('name', '')
        self._navigationURL = framePayload.get('url', '')
        self._url = framePayload.get('url', '')

    def _navigatedWithinDocument(self, url: str) -> None:
        self._url = url

    def _onLifecycleEvent(self, loaderId: str, name: str) -> None:
        if name == 'init':
            self._loaderId = loaderId
            self._lifecycleEvents.clear()
        else:
            self._lifecycleEvents.add(name)

    def _onLoadingStopped(self) -> None:
        self._lifecycleEvents.add('DOMContentLoaded')
        self._lifecycleEvents.add('load')

    def _detach(self) -> None:
        for waitTask in self._waitTasks:
            waitTask.terminate(
                PageError('waitForFunction failed: frame got detached.'))
        self._detached = True
        if self._parentFrame:
            self._parentFrame._childFrames.remove(self)
        self._parentFrame = None
