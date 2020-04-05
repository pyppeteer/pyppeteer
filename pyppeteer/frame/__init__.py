import asyncio
from pathlib import Path
from typing import Optional, Set, List, Union, Any, Awaitable, TYPE_CHECKING

from pyppeteer import helpers
from pyppeteer.connection import CDPSession
from pyppeteer.domworld import DOMWorld, WaitTask
from pyppeteer.errors import PageError, BrowserError
from pyppeteer.jshandle import ElementHandle, JSHandle
from pyppeteer.models import WaitTargets, JSFunctionArg
from pyppeteer.network_manager import Response


class Frame:
    """Frame class.

    Frame objects can be obtained via :attr:`pyppeteer.page.Page.mainFrame`.
    """

    def __init__(
        self, frameManager: 'FrameManager', client: CDPSession, parentFrame: Optional['Frame'], frameId: str
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

        self.addScriptTag = self.mainWorld.addScriptTag
        self.addStyleTag = self.mainWorld.addStyleTag
        self.evaluate = self.mainWorld.evaluate
        self.evaluateHandle = self.mainWorld.evaluateHandle
        self.querySelector = self.J = self.mainWorld.querySelector
        self.querySelectorAll = self.JJ = self.mainWorld.querySelectorAll
        self.querySelectorAllEval = self.JJeval = self.mainWorld.querySelectorAllEval
        self.querySelectorEval = self.Jeval = self.mainWorld.querySelectorEval
        self.type = self.mainWorld.type
        self.waitForFunction = self.mainWorld.waitForFunction
        self.xpath = self.Jx = self.mainWorld.xpath

        self.click = self.secondaryWorld.click
        self.focus = self.secondaryWorld.focus
        self.hover = self.secondaryWorld.hover
        self.select = self.secondaryWorld.select
        self.setContent = self.secondaryWorld.setContent
        self.tap = self.secondaryWorld.tap

    @property
    async def executionContext(self):
        return await self.mainWorld.executionContext

    @property
    async def content(self):
        return await self.secondaryWorld.content

    @property
    async def title(self):
        return await self.secondaryWorld.title

    async def goto(
        self, url: str, referer: str = None, timeout: float = None, waitUntil: WaitTargets = None
    ) -> Optional[Response]:
        return await self._frameManager.navigateFrame(
            self, url=url, referer=referer, timeout=timeout, waitUntil=waitUntil
        )

    async def waitForNavigation(
        self, timeout: Optional[float] = None, waitUntil: Optional[WaitTargets] = None
    ) -> Optional[Response]:
        return await self._frameManager.waitForFrameNavigation(self, waitUntil=waitUntil, timeout=timeout)

    @property
    def mainWorld(self) -> 'DOMWorld':  # ensure mainWorld not settable
        return self._mainWorld

    @property
    def secondaryWorld(self) -> 'DOMWorld':  # ensure secondaryWorld is not settable
        return self._secondaryWorld

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

    async def addScriptTag(self, url=None, path=None, content=None, type='') -> ElementHandle:
        """Add script tag to this frame.

        Details see :meth:`pyppeteer.page.Page.addScriptTag`.
        """
        return await self._mainWorld.addScriptTag(url=url, path=path, content=content, _type=type)

    async def addStyleTag(
        self, url: Optional[str] = None, path: Optional[Union[str, Path]] = None, content: Optional[str] = None
    ) -> Optional['ElementHandle']:
        return await self._mainWorld.addStyleTag(url=url, path=path, content=content)

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
        for index, value in values:
            if not isinstance(value, str):
                raise TypeError(f'Values must be string. Found {value} of type {type(value)} at index {index}')
        return await self.querySelectorEval(  # type: ignore
            selector,
            '''
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
        ''',
            # todo (mattwmaster58): investigate *args vs args usage here
            *values,
        )  # noqa: E501

    async def tap(self, selector: str) -> None:
        """Tap the element which matches the ``selector``.

        Details see :meth:`pyppeteer.page.Page.tap`.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.tap()
        await handle.dispose()

    async def type(self, selector: str, text: str, delay: float = 0) -> None:
        """Type ``text`` on the element which matches ``selector``.

        Details see :meth:`pyppeteer.page.Page.type`.
        """
        handle = await self.querySelector(selector)
        if handle is None:
            raise PageError(f'Cannot find {selector} on this page')
        await handle.type(text, delay)
        await handle.dispose()

    def waitFor(
        self, selectorOrFunctionOrTimeout: Union[str, int, float], *args: JSFunctionArg, **kwargs: Any
    ) -> Awaitable[Optional[JSHandle]]:
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
            return self._client.loop.create_task(asyncio.sleep(selectorOrFunctionOrTimeout / 1000))
        if helpers.is_js_func(selectorOrFunctionOrTimeout):
            return self.waitForFunction(selectorOrFunctionOrTimeout, *args, **kwargs)
        f = self._client.loop.create_future()
        f.set_exception(BrowserError(f'Unsupported target type: {type(selectorOrFunctionOrTimeout)}'))
        return f

    async def waitForSelector(
        self, selector: str, visible: bool = False, hidden: bool = False, timeout: float = None
    ) -> Optional['ElementHandle']:
        """Wait until element which matches ``selector`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForSelector`.
        """
        handle = await self._secondaryWorld.waitForSelector(selector, visible=visible, hidden=hidden, timeout=timeout)
        if handle:
            mainExecutionContext = await self._mainWorld.executionContext
            result = await mainExecutionContext._adoptElementHandle(handle)
            await handle.dispose()
            return result

    async def waitForXPath(
        self, xpath: str, visible: bool = False, hidden: bool = False, timeout: int = None
    ) -> Optional['ElementHandle']:
        """Wait until element which matches ``xpath`` appears on page.

        Details see :meth:`pyppeteer.page.Page.waitForXPath`.
        """
        handle = await self._secondaryWorld.waitForXpath(xpath, visible=visible, hidden=hidden, timeout=timeout)
        if not handle:
            return None
        mainExecutionContext = await self._mainWorld.executionContext
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
        self.mainWorld._detach()
        self.secondaryWorld._detach()
        if self._parentFrame:
            self._parentFrame._childFrames.remove(self)
        self._parentFrame = None


from pyppeteer.frame.frame_manager import FrameManager
