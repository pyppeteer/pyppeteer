#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from pyee import AsyncIOEventEmitter
from pyppeteer.timeout_settings import TimeoutSettings

from pyppeteer import helpers
from pyppeteer.connection import CDPSession
from pyppeteer.errors import BrowserError, ElementHandleError, PageError
from pyppeteer.events import Events
from pyppeteer.frame import Frame
from pyppeteer.lifecycle_watcher import LifecycleWatcher
from pyppeteer.models import WaitTargets
from pyppeteer.network_manager import NetworkManager, Response
from pyppeteer.execution_context import ExecutionContext

if TYPE_CHECKING:
    from pyppeteer.page import Page

logger = logging.getLogger(__name__)

UTILITY_WORLD_NAME = '__pyppeteer_utility_world__'
EVALUATION_SCRIPT_URL = '__pyppeteer_evaluation_script__'
SOURCE_URL_REGEX = re.compile(r'^[ \t]*//[@#] sourceURL=\s*(\S*?)\s*$', re.MULTILINE,)


class FrameManager(AsyncIOEventEmitter):
    """FrameManager class."""

    def __init__(
        self, client: CDPSession, page: 'Page', ignoreHTTPSErrors: bool, timeoutSettings: TimeoutSettings
    ) -> None:
        """Make new frame manager."""
        super().__init__()
        self._client = client
        self._page = page
        self._networkManager = NetworkManager(client, ignoreHTTPSErrors, self)
        self._timeoutSettings = timeoutSettings
        self._mainFrame: Optional[Frame] = None
        self._frames: Dict[Any, Frame] = {}
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

    async def initialize(self) -> None:
        await self._client.send('Page.enable')
        frameTree = (await self._client.send('Page.getFrameTree'))['frameTree']
        self._handleFrameTree(frameTree)

        async def runtime_enabled() -> None:
            await self._client.send('Runtime.enable', {})
            await self._ensureIsolatedWorld(UTILITY_WORLD_NAME)

        await asyncio.gather(
            self._client.send('Page.setLifecycleEventsEnabled', {'enabled': True}),
            runtime_enabled(),
            self._networkManager.initialize(),
        )

    @property
    def networkManager(self) -> NetworkManager:
        return self._networkManager

    async def navigateFrame(
        self, frame: 'Frame', url: str, referer: str = None, timeout: float = None, waitUntil: WaitTargets = None,
    ) -> Optional[Response]:
        ensureNewDocumentNavigation = False

        async def navigate(url_: str, referer_: Optional[str], frameId: str) -> Optional[Exception]:
            try:
                response = await self._client.send(
                    'Page.navigate', {'url': url_, 'referer': referer_, 'frameId': frameId}
                )
                nonlocal ensureNewDocumentNavigation
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
        error = await helpers.future_race(navigate(url, referer, frame._id), watcher.timeoutOrTerminationFuture)
        if not error:
            if ensureNewDocumentNavigation:
                nav_fut = watcher.newDocumentNavigationFuture
            else:
                nav_fut = watcher.sameDocumentNavigationFuture
            error = await helpers.future_race(watcher.timeoutOrTerminationFuture, nav_fut)
        watcher.dispose()
        if error:
            raise error
        return watcher.navigationResponse()

    async def waitForFrameNavigation(
        self, frame: 'Frame', waitUntil: WaitTargets = None, timeout: float = None
    ) -> Optional[Response]:
        if not waitUntil:
            waitUntil = ['load']
        if not timeout:
            timeout = self._timeoutSettings.navigationTimeout
        watcher = LifecycleWatcher(self, frame=frame, timeout=timeout, waitUntil=waitUntil)
        error = await helpers.future_race(
            watcher.timeoutOrTerminationFuture,
            watcher.sameDocumentNavigationFuture,
            watcher.newDocumentNavigationFuture,
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
        for child in frameTree.get('childFrames', []):
            self._handleFrameTree(child)

    @property
    def page(self) -> 'Page':
        return self._page

    @property
    def mainFrame(self) -> Optional['Frame']:
        """Return main frame."""
        return self._mainFrame

    @property
    def frames(self) -> List['Frame']:
        """Return all frames."""
        return list(self._frames.values())

    def frame(self, frameId: Optional[str]) -> Optional['Frame']:
        """Return :class:`Frame` of ``frameId``."""
        return self._frames.get(frameId)

    def _onFrameAttached(self, frameId: str, parentFrameId: str) -> None:
        if frameId in self._frames:
            return
        parentFrame = self._frames.get(parentFrameId)
        frame = Frame(frameManager=self, client=self._client, parentFrame=parentFrame, frameId=frameId)
        self._frames[frameId] = frame
        self.emit(Events.FrameManager.FrameAttached, frame)

    def _onFrameNavigated(self, framePayload: dict) -> None:
        isMainFrame = not framePayload.get('parentId')
        if isMainFrame:
            frame = self._mainFrame
        else:
            frame = self._frames.get(framePayload.get('id', ''))
        if not (isMainFrame or frame):
            raise PageError('We either navigate top level or have old version of the navigated frame')

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
                frame = Frame(frameManager=self, client=self._client, parentFrame=None, frameId=_id)
            self._frames[_id] = frame
            self._mainFrame = frame

        # Update frame payload.
        frame._navigated(framePayload)  # type: ignore
        self.emit(Events.FrameManager.FrameNavigated, frame)

    async def _ensureIsolatedWorld(self, name: str) -> None:
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
                logger.exception(f'An exception occurred: {result}')

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
            if auxData and auxData['isDefault']:
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

    def _onExecutionContextDestroyed(self, executionContextId: int) -> None:
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

    def executionContextById(self, contextId: int) -> 'ExecutionContext':
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
