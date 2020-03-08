#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Frame Manager module."""

import asyncio
import re
import logging
from typing import Any, Awaitable, Dict, List, Optional, Set, Union, Literal

from pyee import EventEmitter

from pyppeteer import helper
from pyppeteer.domworld import DOMWorld, WaitTask
from pyppeteer.events import Events
from pyppeteer.helper import debugError
from pyppeteer.jshandle import JSHandle, ElementHandle
from pyppeteer.connection import CDPSession
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
SOURCE_URL_REGEX = re.compile(r'^[ \t]*//[@#] sourceURL=\s*(\S*?)\s*$', re.MULTILINE,)


class FrameManager(EventEmitter):
    """FrameManager class."""

    def __init__(
        self, client: CDPSession, page: Any, ignoreHTTPSErrors: bool, timeoutSettings: 'TimeoutSettings'
    ) -> None:
        """Make new frame manager."""
        super().__init__()
        self._client = client
        self._page = page
        self._networkManager = NetworkManager(client, ignoreHTTPSErrors, self)
        self._timeoutSettings = timeoutSettings
        self._frames = {}
        self._contextIdToContext: Dict[int, ExecutionContext] = {}
        self._isolatedWorlds: Set[str] = set()

        client.on(
            'Page.frameAttached',
            lambda event: self._onFrameAttached(event.get('frameId', ''), event.get('parentFrameId', '')),
        )
        client.on('Page.frameNavigated', lambda event: self._onFrameNavigated(event.get('frame')))
        client.on(
            'Page.navigatedWithinDocument',
            lambda event: self._onFrameNavigatedWithinDocument(event.get('frameId'), event.get('url')),
        )
        client.on('Page.frameDetached', lambda event: self._onFrameDetached(event.get('frameId')))
        client.on('Page.frameStoppedLoading', lambda event: self._onFrameStoppedLoading(event.get('frameId')))
        client.on(
            'Runtime.executionContextCreated', lambda event: self._onExecutionContextCreated(event.get('context'))
        )
        client.on(
            'Runtime.executionContextDestroyed',
            lambda event: self._onExecutionContextDestroyed(event.get('executionContextId')),
        )
        client.on('Runtime.executionContextsCleared', lambda event: self._onExecutionContextsCleared())
        client.on('Page.lifecycleEvent', lambda event: self._onLifecycleEvent(event))

        # aliases

    async def initiliaze(self):
        frameTree = await asyncio.gather(self._client.send('Page.enable'), self._client.send('Page.getFrameTree'),)
        self._handleFrameTree(frameTree)

        async def runtime_enabled():
            await self._client.send('Runtime.enable', {})
            await self._ensureIsolatedWorld(UTILITY_WORLD_NAME)

        await asyncio.gather(
            self._client.send('Page.setLifecycleEventsEnabled', {'enabled': True}),
            runtime_enabled(),
            await self._networkManager.initialize(),
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
                    'Page.navigate', {'url': url, 'referer': referer, 'frameId': frameId,}
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

        watcher = LifecycleWatcher(self, frame=frame, timeout=timeout, waitUntil=waitUntil)
        error = await asyncio.wait(
            [navigate(url, referer, frame._id), watcher.timeoutOrTerminationPromise()],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not error:
            if ensureNewDocumentNavigation:
                nav_promise = watcher.newDocumentNavigationPromise()
            else:
                nav_promise = watcher.sameDocumentNavigationPromise()
            error = await asyncio.wait(
                [watcher.timeoutOrTerminationPromise(), nav_promise,], return_when=asyncio.FIRST_COMPLETED
            )
        watcher.dispose()
        if error:
            raise error
        return watcher.navigationResponse()

    async def waitForFrameNavigation(
        self, frame: 'Frame', waitUntil: Union[str, List[str]] = None, timeout: int = None
    ):
        if not waitUntil:
            waitUntil = ['load']
        if not timeout:
            timeout = self._timeoutSettings.navigationTimeout
        watcher = LifecycleWatcher(self, frame, waitUntil, timeout)
        error = asyncio.wait(
            [
                watcher.timeoutOrTerminationPromise(),
                watcher.sameDocumentNavigationPromise(),
                watcher.newDocumentNavigationPromise(),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
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
                frame['id'], frame['parentId'],
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

    @property
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
            raise PageError('We either navigate top level or have old version ' 'of the navigated frame')

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
            {'source': f'//# sourceURL={EVALUATION_SCRIPT_URL}', 'worldName': name,},
        )
        results = await asyncio.gather(
            *[
                self._client.send(
                    'Page.createIsolatedWorld', {'frameId': frame._id, 'grantUniversalAccess': True, 'worldName': name,}
                )
                for frame in self.frames
            ],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                debugError(logger, result)

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
            elif contextPayload.get('name') == UTILITY_WORLD_NAME and not frame._secondaryWorld._hasContext():
                # In case of multiple sessions to the same target, there's a race between
                # connections so we might end up creating multiple isolated worlds.
                # We can use either.
                world = frame._secondaryWorld
        if auxData and auxData.get('type') == 'isolated':
            self._isolatedWorlds.add(contextPayload['name'])

        context = ExecutionContext(self._client, contextPayload, world)
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
            raise ElementHandleError(f'INTERNAL ERROR: missing context with id = {contextId}')
        return context

    def _removeFramesRecursively(self, frame: 'Frame') -> None:
        for child in frame.childFrames:
            self._removeFramesRecursively(child)
        frame._detach()
        self._frames.pop(frame._id, None)
        self.emit(Events.FrameManager.FrameDetached, frame)


class Frame:
    """Frame class.

    Frame objects can be obtained via :attr:`pyppeteer.page.Page.mainFrame`.
    """

    def __init__(
        self, frameManager: FrameManager, client: CDPSession, parentFrame: Optional['Frame'], frameId: str
    ) -> None:
        self._frameManager = frameManager
        self._client = client
        self._parentFrame = parentFrame
        self._url = ''
        self._id = frameId
        self._detached = False

        self._loaderId = ''
        self._lifecycleEvents: Set[str] = set()
        self._mainWorld = DOMWorld(frameManager, self, frameManager._timeoutSettings)
        self._secondaryWorld = DOMWorld(frameManager, self, frameManager._timeoutSettings)
        self._childFrames: Set[Frame] = set()  # maybe list
        if self._parentFrame:
            self._parentFrame._childFrames.add(self)

        self._waitTasks: Set[WaitTask] = set()  # maybe list
        if self._parentFrame:
            self._parentFrame._childFrames.add(self)

        # aliases
        self.goto = self._frameManager.navigateFrame
        self.waitForSelector = self._frameManager.waitForFrameNavigation
        self.click = self._secondaryWorld.click
        self.executionContext = self._mainWorld.executionContext
        self.evaluateHandle = self.executionContext.evaluateHandle
        self.evaluate = self.executionContext.evaluate
        self.querySelector = self.J = self._mainWorld.querySelector
        self.xpath = self.Jx = self._mainWorld.xpath
        self.querySelectorEval = self.Jeval = self._mainWorld.querySelectorEval
        self.querySelectorAllEval = self.JJeval = self._mainWorld.querySelectorAllEval
        self.addScriptTag = self._mainWorld.addScriptTag
        self.addStyleTag = self._mainWorld.addStyleTag
        self.click = self._secondaryWorld.click
        self.focus = self._secondaryWorld.focus
        self.hover = self._secondaryWorld.hover
        self.select = self._secondaryWorld.select
        self.tap = self._secondaryWorld.tap
        self.type = self._mainWorld.type
        self.waitForFunction = self._mainWorld.waitForFunction
        self.title = self._secondaryWorld.title
        self.content = self._secondaryWorld.content
        self.setContent = self._secondaryWorld.setContent

    @property
    def name(self) -> str:
        """Get frame name."""
        return getattr(self, '_name', '')

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

    @property
    def isDetached(self) -> bool:
        """Return ``True`` if this frame is detached.

        Otherwise return ``False``.
        """
        return self._detached

    def waitFor(
        self, selectorOrFunctionOrTimeout: Union[str, int, float], *args: Any, **kwargs: Any
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
            return self._client._loop.create_task(asyncio.sleep(selectorOrFunctionOrTimeout / 1000))
        if helper.is_jsfunc(selectorOrFunctionOrTimeout):
            return self.waitForFunction(selectorOrFunctionOrTimeout, *args, **kwargs)
        f = self._client._loop.create_future()
        f.set_exception(BrowserError(f'Unsupported target type:' f' {type(selectorOrFunctionOrTimeout)}'))
        return f

    async def waitForSelector(self, selector, visible=False, hidden=False, timeout=None) -> Optional['ElementHandle']:
        """Wait until element which matches ``selector`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForSelector`.
        """
        handle = await self._secondaryWorld.waitForSelector(selector, visible=visible, hidden=hidden, timeout=timeout)
        if handle:
            mainExecutionContext = await self._mainWorld.executionContext()
            result = await mainExecutionContext._adoptElementHandle()
            await handle.dispose()
            return result

    async def waitForXpath(self, xpath, visible=False, hidden=False, timeout: int = None):
        """Wait until element which matches ``xpath`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForXPath`.
        """
        handle = await self._secondaryWorld.waitForXpath(xpath, visible=visible, hidden=hidden, timeout=timeout)
        if not handle:
            return None
        mainExecutionContext = await self._mainWorld.executionContext()
        result = await mainExecutionContext._adoptElementHandle(handle)
        await handle.dispose()
        return result

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
        self._detached = True
        self._mainWorld._detach()
        self._secondaryWorld._detach()
        if self._parentFrame:
            self._parentFrame._childFrames.remove(self)
        self._parentFrame = None
