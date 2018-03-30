#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Page module."""

import asyncio
import base64
import json
import logging
import math
import mimetypes
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from typing import TYPE_CHECKING

from pyee import EventEmitter

from pyppeteer import helper
from pyppeteer.connection import CDPSession
from pyppeteer.coverage import Coverage
from pyppeteer.dialog import Dialog
from pyppeteer.element_handle import ElementHandle  # noqa: F401
from pyppeteer.emulation_manager import EmulationManager
from pyppeteer.errors import PageError
from pyppeteer.execution_context import JSHandle  # noqa: F401
from pyppeteer.frame_manager import Frame  # noqa: F401
from pyppeteer.frame_manager import FrameManager
from pyppeteer.input import Keyboard, Mouse, Touchscreen
from pyppeteer.navigator_watcher import NavigatorWatcher
from pyppeteer.network_manager import NetworkManager, Response, Request
from pyppeteer.tracing import Tracing
from pyppeteer.util import merge_dict

if TYPE_CHECKING:
    from pyppeteer.browser import Target  # noqa: F401

logger = logging.getLogger(__name__)


class Page(EventEmitter):
    """Page class.

    This class provides methods to interact with a single tab of chrome. One
    :class:`~pyppeteer.browser.Browser` object might have multiple Page object.

    The :class:`Page` class emits various :attr:`~Page.Events` which can be
    handled by using ``on`` or ``once`` method, which is inherited from
    `pyee <https://pyee.readthedocs.io/en/latest/>`_'s ``EventEmitter`` class.
    """

    #: Available events.
    Events = SimpleNamespace(
        Console='console',
        Dialog='dialog',
        Error='error',
        PageError='pageerror',
        Request='request',
        Response='response',
        RequestFailed='requestfailed',
        RequestFinished='requestfinished',
        FrameAttached='frameattached',
        FrameDetached='framedetached',
        FrameNavigated='framenavigated',
        Load='load',
        Metrics='metrics',
    )

    PaperFormats: Dict[str, Dict[str, float]] = dict(
        letter={'width': 8.5, 'height': 11},
        legal={'width': 8.5, 'height': 14},
        tabloid={'width': 11, 'height': 17},
        ledger={'width': 17, 'height': 11},
        a0={'width': 33.1, 'height': 46.8},
        a1={'width': 23.4, 'height': 33.1},
        a2={'width': 16.5, 'height': 23.4},
        a3={'width': 11.7, 'height': 16.5},
        a4={'width': 8.27, 'height': 11.7},
        a5={'width': 5.83, 'height': 8.27},
    )

    @staticmethod
    async def create(client: CDPSession, target: 'Target',
                     ignoreHTTPSErrors: bool = False, appMode: bool = False,
                     screenshotTaskQueue: list = None) -> 'Page':
        """Async function which makes new page object."""
        await client.send('Page.enable'),
        frameTree = (await client.send('Page.getFrameTree'))['frameTree']
        page = Page(client, target, frameTree, ignoreHTTPSErrors,
                    screenshotTaskQueue)

        await asyncio.wait([
            client.send('Page.setLifecycleEventsEnabled', {'enabled': True}),
            client.send('Network.enable', {}),
            client.send('Runtime.enable', {}),
            client.send('Security.enable', {}),
            client.send('Performance.enable', {}),
        ])
        if ignoreHTTPSErrors:
            await client.send('Security.setOverrideCertificateErrors',
                              {'override': True})
        if not appMode:
            await page.setViewport({'width': 800, 'height': 600})
        return page

    def __init__(self, client: CDPSession, target: 'Target', frameTree: Dict,
                 ignoreHTTPSErrors: bool = False,
                 screenshotTaskQueue: list = None,
                 ) -> None:
        super().__init__()
        self._client = client
        self._target = target
        self._keyboard = Keyboard(client)
        self._mouse = Mouse(client, self._keyboard)
        self._touchscreen = Touchscreen(client, self._keyboard)
        self._frameManager = FrameManager(client, frameTree, self)
        self._networkManager = NetworkManager(client, self._frameManager)
        self._emulationManager = EmulationManager(client)
        self._tracing = Tracing(client)
        self._pageBindings: Dict[str, Callable] = dict()
        self._ignoreHTTPSErrors = ignoreHTTPSErrors
        self._defaultNavigationTimeout = 30000  # milliseconds
        self._coverage = Coverage(client)

        if screenshotTaskQueue is None:
            screenshotTaskQueue = list()
        self._screenshotTaskQueue = screenshotTaskQueue

        _fm = self._frameManager
        _fm.on(FrameManager.Events.FrameAttached,
               lambda event: self.emit(Page.Events.FrameAttached, event))
        _fm.on(FrameManager.Events.FrameDetached,
               lambda event: self.emit(Page.Events.FrameDetached, event))
        _fm.on(FrameManager.Events.FrameNavigated,
               lambda event: self.emit(Page.Events.FrameNavigated, event))

        _nm = self._networkManager
        _nm.on(NetworkManager.Events.Request,
               lambda event: self.emit(Page.Events.Request, event))
        _nm.on(NetworkManager.Events.Response,
               lambda event: self.emit(Page.Events.Response, event))
        _nm.on(NetworkManager.Events.RequestFailed,
               lambda event: self.emit(Page.Events.RequestFailed, event))
        _nm.on(NetworkManager.Events.RequestFinished,
               lambda event: self.emit(Page.Events.RequestFinished, event))

        client.on('Page.loadEventFired',
                  lambda event: self.emit(Page.Events.Load))
        client.on('Runtime.consoleAPICalled',
                  lambda event: self._onConsoleAPI(event))
        client.on('Page.javascriptDialogOpening',
                  lambda event: self._onDialog(event))
        client.on('Runtime.exceptionThrown',
                  lambda exception: self._handleException(
                      exception.get('exceptionDetails')))
        client.on('Security.certificateError',
                  lambda event: self._onCertificateError(event))
        client.on('Inspector.targetCrashed',
                  lambda event: self._onTargetCrashed())
        client.on('Performance.metrics',
                  lambda event: self._emitMetrics(event))

    @property
    def target(self) -> 'Target':
        """Return a target this page created from."""
        return self._target

    def _onTargetCrashed(self, *args: Any, **kwargs: Any) -> None:
        self.emit('error', PageError('Page crashed!'))

    @property
    def mainFrame(self) -> Optional['Frame']:
        """Get main :class:`~pyppeteer.frame_manager.Frame` of this page."""
        return self._frameManager._mainFrame

    @property
    def keyboard(self) -> Keyboard:
        """Get :class:`~pyppeteer.input.Keyboard` object."""
        return self._keyboard

    @property
    def touchscreen(self) -> Touchscreen:
        """Get :class:`~pyppeteer.input.Touchscreen` object."""
        return self._touchscreen

    @property
    def coverage(self) -> Coverage:
        """Return :class:`~pyppeteer.coverage.Coverage`."""
        return self._coverage

    async def tap(self, selector: str) -> None:
        """Tap the element which matches the ``selector``.

        :arg str selector: A selector to search element to touch.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.tap()
        await handle.dispose()

    @property
    def tracing(self) -> 'Tracing':
        """Get tracing object."""
        return self._tracing

    @property
    def frames(self) -> List['Frame']:
        """Get all frames of this page."""
        return list(self._frameManager.frames())

    async def setRequestInterception(self, value: bool) -> None:
        """Enable/disable request interception."""
        return await self._networkManager.setRequestInterception(value)

    async def setOfflineMode(self, enabled: bool) -> None:
        """Set offline mode enable/disable."""
        await self._networkManager.setOfflineMode(enabled)

    def setDefaultNavigationTimeout(self, timeout: int) -> None:
        """Change the default maximum navigation timeout.

        This method changes the default timeout of 30 seconds for the following
        methods:

        * :meth:`goto`
        * :meth:`goBack`
        * :meth:`goForward`
        * :meth:`reload`
        * :meth:`waitForNavigation`

        :arg int timeout: Maximum navigation time in milliseconds.
        """
        self._defaultNavigationTimeout = timeout

    def _onCertificateError(self, event: Any) -> None:
        if not self._ignoreHTTPSErrors:
            return
        asyncio.ensure_future(
            self._client.send('Security.handleCertificateError', {
                'eventId': event.get('eventId'),
                'action': 'continue'
            })
        )

    async def querySelector(self, selector: str) -> Optional['ElementHandle']:
        """Get an Element which matches ``selector``.

        :arg str selector: A selector to search element.
        :return Optional[ElementHandle]: If element which matches the
            ``selector`` is found, return its
            :class:`~pyppeteer.element_handle.ElementHandle`. If not found,
            returns ``None``.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.querySelector(selector)

    async def evaluateHandle(self, pageFunction: str, *args: Any
                             ) -> JSHandle:
        """Execute function on this page.

        Difference between :meth:`~pyppeteer.page.Page.evaluate` and
        :meth:`~pyppeteer.page.Page.evaluateHandle` is that
        ``evaluateHandle`` returns JSHandle object (not value).

        :arg str pageFunction: JavaScript function to be executed.
        """
        if not self.mainFrame:
            raise PageError('no main frame.')
        context = await self.mainFrame.executionContext()
        if not context:
            raise PageError('No context.')
        return await context.evaluateHandle(pageFunction, *args)

    async def queryObjects(self, prototypeHandle: JSHandle) -> JSHandle:
        """Iterate js heap and finds all the objects with the handle.

        :arg JSHandle prototypeHandle: JSHandle of prototype object.
        """
        if not self.mainFrame:
            raise PageError('no main frame.')
        context = await self.mainFrame.executionContext()
        if not context:
            raise PageError('No context.')
        return await context.queryObjects(prototypeHandle)

    async def querySelectorEval(self, selector: str, pageFunction: str,
                                *args: Any) -> Optional[Any]:
        """Execute function with an element which matches ``selector``.

        :arg str selector: A selector to query page for.
        :arg str pageFunction: String of JavaScript function to be evaluated on
                               browser. This function takes an element which
                               matches the selector as a first argument.
        :arg Any args: Arguments to pass to ``pageFunction``.

        This method raises error if no element matched the ``selector``.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.querySelectorEval(selector, pageFunction, *args)

    async def querySelectorAllEval(self, selector: str, pageFunction: str,
                                   *args: Any) -> Optional[Any]:
        """Execute function with all elements which matches ``selector``.

        :arg str selector: A selector to query page for.
        :arg str pageFunction: String of JavaScript function to be evaluated on
                               browser. This function takes Array of the
                               matched elements as the first argument.
        :arg Any args: Arguments to pass to ``pageFunction``.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.querySelectorAllEval(selector, pageFunction, *args)

    async def querySelectorAll(self, selector: str) -> List['ElementHandle']:
        """Get all element which matches `selector` as a list.

        :arg str selector: A selector to search element.
        :return List[ElementHandle]: List of
            :class:`~pyppeteer.element_handle.ElementHandle` which matches the
            ``selector``. If no element is matched to the ``selector``, return
            empty list.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.querySelectorAll(selector)

    async def xpath(self, expression: str) -> List[ElementHandle]:
        """Evaluate XPath expression.

        If there is no such element in this page, return None.

        :arg str expression: XPath string to be evaluated.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.xpath(expression)

    #: alias to :meth:`querySelector`
    J = querySelector
    #: alias to :meth:`querySelectorEval`
    Jeval = querySelectorEval
    #: alias to :meth:`querySelectorAll`
    JJ = querySelectorAll
    #: alias to :meth:`querySelectorAllEval`
    JJeval = querySelectorAllEval
    #: alias to :meth:`xpath`
    Jx = xpath

    async def cookies(self, *urls: str) -> dict:
        """Get cookies."""
        if not urls:
            urls = (self.url, )
        resp = await self._client.send('Network.getCookies', {
            'urls': urls,
        })
        return resp.get('cookies', {})

    async def deleteCookie(self, *cookies: dict) -> None:
        """Delete cookie."""
        pageURL = self.url
        for cookie in cookies:
            item = dict(**cookie)
            if not cookie.get('url') and pageURL.startswith('http'):
                item['url'] = pageURL
            await self._client.send('Network.deleteCookies', item)

    async def setCookie(self, *cookies: dict) -> None:
        """Set cookies."""
        pageURL = self.url
        startsWithHTTP = pageURL.startswith('http')
        items = []
        for cookie in cookies:
            item = dict(**cookie)
            if 'url' not in item and startsWithHTTP:
                item['url'] = pageURL
            if item.get('url') == 'about:blank':
                name = item.get('name', '')
                raise PageError(f'Blank page can not have cookie "{name}"')
            if item.get('url', '').startswith('data:'):
                name = item.get('name', '')
                raise PageError(f'Data URL page can not have cookie "{name}"')
            items.append(item)
        await self.deleteCookie(*items)
        if items:
            await self._client.send('Network.setCookies', {
                'cookies': items,
            })

    async def addScriptTag(self, options: Dict = None, **kwargs: str
                           ) -> ElementHandle:
        """Add script tag to this page.

        One of ``url``, ``path`` or ``content`` option is necessary.
            * ``url`` (string): URL of a script to add.
            * ``path`` (string): Path to the local JavaScript file to add.
            * ``content`` (string): JavaScript string to add.

        :return ElementHandle: :class:`~pyppeteer.element_handle.ElementHandle`
                               of added tag.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        options = merge_dict(options, kwargs)
        return await frame.addScriptTag(options)

    async def addStyleTag(self, options: Dict = None, **kwargs: str
                          ) -> ElementHandle:
        """Add style or link tag to this page.

        One of ``url``, ``path`` or ``content`` option is necessary.
            * ``url`` (string): URL of the link tag to add.
            * ``path`` (string): Path to the local CSS file to add.
            * ``content`` (string): CSS string to add.

        :return ElementHandle: :class:`~pyppeteer.element_handle.ElementHandle`
                               of added tag.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        options = merge_dict(options, kwargs)
        return await frame.addStyleTag(options)

    async def injectFile(self, filePath: str) -> str:
        """[Deprecated] Inject file to this page.

        This method is deprecated. Use :meth:`addScriptTag` instead.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.injectFile(filePath)

    async def exposeFunction(self, name: str, pyppeteerFunction: Callable
                             ) -> None:
        """Add python function to the browser's ``window`` object as ``name``.

        Registered function can be called from chrome process.

        :arg string name: Name of the function on the window object.
        :arg Callable pyppeteerFunction: Function which will be called on
                                         python process.
        """
        if self._pageBindings.get(name):
            raise PageError(f'Failed to add page binding with name {name}: '
                            f'window["{name}"] already exists!')
        self._pageBindings[name] = pyppeteerFunction

        addPageBinding = '''
function addPageBinding(bindingName) {
  window[bindingName] = async(...args) => {
    const me = window[bindingName];
    let callbacks = me['callbacks'];
    if (!callbacks) {
      callbacks = new Map();
      me['callbacks'] = callbacks;
    }
    const seq = (me['lastSeq'] || 0) + 1;
    me['lastSeq'] = seq;
    const promise = new Promise(fulfill => callbacks.set(seq, fulfill));
    // eslint-disable-next-line no-console
    console.debug('driver:page-binding', JSON.stringify({name: bindingName, seq, args}));
    return promise;
  };
}
        '''  # noqa: E501
        expression = helper.evaluationString(addPageBinding, name)
        await self._client.send('Page.addScriptToEvaluateOnNewDocument',
                                {'source': expression})
        await asyncio.wait([
            frame.evaluate(expression, force_expr=True)
            for frame in self.frames
        ])

    async def authenticate(self, credentials: Dict[str, str]) -> Any:
        """Provide credentials for http authentication.

        ``credentials`` should be ``None`` or dict which has ``username`` and
        ``password`` field.
        """
        return await self._networkManager.authenticate(credentials)

    async def setExtraHTTPHeaders(self, headers: Dict[str, str]) -> None:
        """Set extra http headers."""
        return await self._networkManager.setExtraHTTPHeaders(headers)

    async def setUserAgent(self, userAgent: str) -> None:
        """Set user agent to use in this page."""
        return await self._networkManager.setUserAgent(userAgent)

    async def metrics(self) -> Dict[str, Any]:
        """Get metrics."""
        response = await self._client.send('Performance.getMetrics')
        return self._buildMetricsObject(response['metrics'])

    def _emitMetrics(self, event: Dict) -> None:
        self.emit(Page.Events.Metrics, {
            'title': event['title'],
            'metrics': self._buildMetricsObject(event['metrics']),
        })

    def _buildMetricsObject(self, metrics: List) -> Dict[str, Any]:
        result = {}
        for metric in metrics or []:
            if metric['name'] in supportedMetrics:
                result[metric['name']] = metric['value']
        return result

    def _handleException(self, exceptionDetails: Dict) -> None:
        message = helper.getExceptionMessage(exceptionDetails)
        self.emit(Page.Events.PageError, PageError(message))

    def _onConsoleAPI(self, event: dict) -> None:
        _args = event.get('args', [])
        if (event.get('type') == 'debug' and _args and
                _args[0]['value'] == 'driver:page-binding'):
            obj = json.loads(_args[1]['value'])
            name = obj.get('name')
            seq = obj.get('seq')
            args = obj.get('args')
            result = self._pageBindings[name](*args)

            deliverResult = '''
function deliverResult(name, seq, result) {
  window[name]['callbacks'].get(seq)(result);
  window[name]['callbacks'].delete(seq);
}
            '''
            expression = helper.evaluationString(
                deliverResult, name, seq, result)
            asyncio.ensure_future(self._client.send('Runtime.evaluate', {
                'expression': expression,
                'contextId': event['executionContextId'],
            }))
            return

        if not self.listeners(Page.Events.Console):
            for arg in _args:
                asyncio.ensure_future(helper.releaseObject(self._client, arg))
            return

        _id = event['executionContextId']
        values = []
        for arg in _args:
            values.append(self._frameManager.createJSHandle(_id, arg))

        textTokens = []
        for arg, value in zip(_args, values):
            if arg.get('objectId'):
                textTokens.append(value.toString())
            else:
                textTokens.append(str(helper.valueFromRemoteObject(arg)))

        message = ConsoleMessage(event['type'], ' '.join(textTokens), values)
        self.emit(Page.Events.Console, message)

    def _onDialog(self, event: Any) -> None:
        dialogType = ''
        _type = event.get('type')
        if _type == 'alert':
            dialogType = Dialog.Type.Alert
        elif (_type == 'confirm'):
            dialogType = Dialog.Type.Confirm
        elif (_type == 'prompt'):
            dialogType = Dialog.Type.Prompt
        elif (_type == 'beforeunload'):
            dialogType = Dialog.Type.BeforeUnload
        dialog = Dialog(self._client, dialogType, event.get('message'),
                        event.get('defaultPrompt'))
        self.emit(Page.Events.Dialog, dialog)

    @property
    def url(self) -> str:
        """Get url of this page."""
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return frame.url

    async def content(self) -> str:
        """Get the whole HTML contents of the page."""
        frame = self._frameManager.mainFrame
        if frame is None:
            raise PageError('No main frame.')
        return await frame.content()

    async def setContent(self, html: str) -> None:
        """Set content to this page."""
        frame = self._frameManager.mainFrame
        if frame is None:
            raise PageError('No main frame.')
        await frame.setContent(html)

    async def goto(self, url: str, options: dict = None, **kwargs: Any
                   ) -> Optional[Response]:
        """Go to the ``url``.

        :arg string url: URL to navigate page to. The url should include
            scheme, e.g. ``https://``.

        Available options are:

        * ``timeout`` (int): Maximum navigation time in milliseconds, defaults
          to 30 seconds, pass ``0`` to desable timeout. The default value can
          be changed by using the :meth:`setDefaultNavigationTimeout` method.
        * ``waitUntil`` (str|List[str]): When to consider navigation succeeded,
          defaults to ``load``. Given a list of event strings, navigation is
          considered to be successful after all events have been fired. Events
          can be either:

          * ``load``: when ``load`` event is fired.
          * ``documentloaded``: when the ``DOMContentLoaded`` event is fired.
          * ``networkidle0``: when there are no more than 0 network connections
            for at least 500 ms.
          * ``networkidle2``: when there are no more than 2 network connections
            for at least 500 ms.
        """
        options = merge_dict(options, kwargs)
        referrer = self._networkManager.extraHTTPHeaders().get('referer', '')
        requests: Dict[str, Request] = dict()
        eventListeners = [helper.addEventListener(
            self._networkManager, NetworkManager.Events.Request,
            lambda request: requests.__setitem__(request.url, request)
        )]

        mainFrame = self._frameManager.mainFrame
        if mainFrame is None:
            raise PageError('No main frame.')
        timeout = options.get('timeout', self._defaultNavigationTimeout)
        watcher = NavigatorWatcher(self._frameManager, mainFrame, timeout,
                                   options)

        result = await self._navigate(url, referrer)
        if result is not None:
            raise PageError(result)
        result = await watcher.navigationPromise()
        watcher.cancel()
        helper.removeEventListeners(eventListeners)
        error = result[0].pop().exception()  # type: ignore
        if error:
            raise error

        request = requests.get(mainFrame.url)
        return request.response if request else None

    async def _navigate(self, url: str, referrer: str) -> Optional[str]:
        response = await self._client.send(
            'Page.navigate', {'url': url, 'referrer': referrer})
        if response.get('errorText'):
            return response['errorText']
        return None

    async def reload(self, options: dict = None, **kwargs: Any
                     ) -> Optional[Response]:
        """Reload this page.

        Available options are same as :meth:`goto` method.
        """
        options = merge_dict(options, kwargs)
        response = (await asyncio.gather(
            self.waitForNavigation(options),
            self._client.send('Page.reload'),
        ))[0]
        return response

    async def waitForNavigation(self, options: dict = None, **kwargs: Any
                                ) -> Optional[Response]:
        """Wait for navigation.

        Available options are same as :meth:`goto` method.
        """
        options = merge_dict(options, kwargs)
        mainFrame = self._frameManager.mainFrame
        if mainFrame is None:
            raise PageError('No main frame.')
        timeout = options.get('timeout', self._defaultNavigationTimeout)
        watcher = NavigatorWatcher(self._frameManager, mainFrame, timeout,
                                   options)
        responses: Dict[str, Response] = dict()
        listener = helper.addEventListener(
            self._networkManager,
            NetworkManager.Events.Response,
            lambda response: responses.__setitem__(response.url, response)
        )
        result = await watcher.navigationPromise()
        helper.removeEventListeners([listener])
        error = result[0].pop().exception()
        if error:
            raise error

        response = responses.get(self.url, None)
        return response

    async def goBack(self, options: dict = None, **kwargs: Any
                     ) -> Optional[Response]:
        """Navigate to the previous page in history.

        Available options are same as :meth:`goto` method.
        """
        options = merge_dict(options, kwargs)
        return await self._go(-1, options)

    async def goForward(self, options: dict = None, **kwargs: Any
                        ) -> Optional[Response]:
        """Navigate to the next page in history.

        Available options are same as :meth:`goto` method.
        """
        options = merge_dict(options, kwargs)
        return await self._go(+1, options)

    async def _go(self, delta: int, options: dict) -> Optional[Response]:
        history = await self._client.send('Page.getNavigationHistory')
        _count = history.get('currentIndex', 0) + delta
        entries = history.get('entries', [])
        if len(entries) <= _count:
            return None
        entry = entries[_count]
        response = (await asyncio.gather(
            self.waitForNavigation(options),
            self._client.send('Page.navigateToHistoryEntry', {
                'entryId': entry.get('id')
            })
        ))[0]
        return response

    async def bringToFront(self) -> None:
        """Bring page to front (activate tab)."""
        await self._client.send('Page.bringToFront')

    async def emulate(self, options: dict = None, **kwargs: Any) -> None:
        """Emulate viewport and user agent."""
        options = merge_dict(options, kwargs)
        # TODO: if options does not have viewport or userAgent,
        # skip its setting.
        await self.setViewport(options.get('viewport', {}))
        await self.setUserAgent(options.get('userAgent', ''))

    async def setJavaScriptEnabled(self, enabled: bool) -> None:
        """Set JavaScript enable/disable."""
        await self._client.send('Emulation.setScriptExecutionDisabled', {
            'value': not enabled,
        })

    async def emulateMedia(self, mediaType: str = None) -> None:
        """Emulate css media type of the page."""
        if mediaType not in ['screen', 'print', None, '']:
            raise ValueError(f'Unsupported media type: {mediaType}')
        await self._client.send('Emulation.setEmulatedMedia', {
            'media': mediaType or '',
        })

    async def setViewport(self, viewport: dict) -> None:
        """Set viewport.

        Available options are:
            * ``width`` (int): page width in pixel.
            * ``height`` (int): page height in pixel.
            * ``deviceScaleFactor`` (float): Default to 1.0.
            * ``isMobile`` (bool): Default to ``False``.
            * ``hasTouch`` (bool): Default to ``False``.
            * ``isLandscape`` (bool): Default to ``False``.
        """
        needsReload = await self._emulationManager.emulateViewport(
            self._client, viewport,
        )
        self._viewport = viewport
        if needsReload:
            await self.reload()

    @property
    def viewport(self) -> dict:
        """Get viewport dict.

        Field of returned dict is same as :meth:`setViewport`.
        """
        return self._viewport

    async def evaluate(self, pageFunction: str, *args: Any,
                       force_expr: bool = False) -> Any:
        """Execute js-function or js-expression on browser and get result.

        :arg str pageFunction: String of js-function/expression to be executed
                               on the browser.
        :arg bool force_expr: If True, evaluate `pageFunction` as expression.
                              If False (default), try to automatically detect
                              function or expression.

        note: ``force_expr`` option is a keyword only argument.
        """
        frame = self._frameManager.mainFrame
        if frame is None:
            raise PageError('No main frame.')
        return await frame.evaluate(pageFunction, *args, force_expr=force_expr)

    async def evaluateOnNewDocument(self, pageFunction: str, *args: str
                                    ) -> None:
        """Add a JavaScript function to the document.

        This function would be invoked in one of the following scenarios:

        * whenever the page is navigated
        * whenever the child frame is attached or navigated. Inthis case, the
          function is invoked in the context of the newly attached frame.
        """
        source = helper.evaluationString(pageFunction, *args)
        await self._client.send('Page.addScriptToEvaluateOnNewDocument', {
            'source': source,
        })

    async def screenshot(self, options: dict = None, **kwargs: Any) -> bytes:
        """Take a screen shot.

        The following options are available:

        * ``path`` (str): The file path to save the image to. The screenshot
          type will be inferred from the file extension.
        * ``type`` (str): Specify screenshot type, can be either ``jpeg`` or
          ``png``. Defaults to ``png``.
        * ``quality`` (int): The quality of the image, between 0-100. Not
          applicable to ``png`` image.
        * ``fullPage`` (bool): When true, take a screenshot of the full
          scrollable page. Defaults to ``False``.
        * ``clip`` (dict): An object which specifies clipping region of the
          page. This option should have the following fields:

          * ``x`` (int): x-coordinate of top-left corner of clip area.
          * ``y`` (int): y-coordinate of top-left corner of clip area.
          * ``width`` (int): width of clipping area.
          * ``height`` (int): height of clipping area.

        * ``omitBackground`` (bool): Hide default white background and allow
          capturing screenshot with transparency.
        """
        options = merge_dict(options, kwargs)
        screenshotType = None
        if 'type' in options:
            screenshotType = options['type']
            if screenshotType not in ['png', 'jpeg']:
                raise ValueError(f'Unknown type value: {screenshotType}')
        elif 'path' in options:
            mimeType, _ = mimetypes.guess_type(options['path'])
            if mimeType == 'image/png':
                screenshotType = 'png'
            elif mimeType == 'image/jpeg':
                screenshotType = 'jpeg'
            else:
                raise ValueError('Unsupported screenshot '
                                 f'mime type: {mimeType}')
        if not screenshotType:
            screenshotType = 'png'
        return await self._screenshotTask(screenshotType, options)

    async def _screenshotTask(self, format: str, options: dict) -> bytes:  # noqa: C901,E501
        await self._client.send('Target.activateTarget', {
            'targetId': self._target._targetId,
        })
        clip = options.get('clip')
        if clip:
            clip['scale'] = 1

        if options.get('fullPage'):
            metrics = await self._client.send('Page.getLayoutMetrics')
            width = math.ceil(metrics['contentSize']['width'])
            height = math.ceil(metrics['contentSize']['height'])

            # Overwrite clip for full page at all times.
            clip = dict(x=0, y=0, width=width, height=height, scale=1)
            mobile = self._viewport.get('isMobile', False)
            deviceScaleFactor = self._viewport.get('deviceScaleFactor', 1)
            landscape = self._viewport.get('isLandscape', False)
            if landscape:
                screenOrientation = dict(angle=90, type='landscapePrimary')
            else:
                screenOrientation = dict(angle=0, type='portraitPrimary')
            await self._client.send('Emulation.setDeviceMetricsOverride', {
                'mobile': mobile,
                'width': width,
                'height': height,
                'deviceScaleFactor': deviceScaleFactor,
                'screenOrientation': screenOrientation,
            })

        if options.get('omitBackground'):
            await self._client.send(
                'Emulation.setDefaultBackgroundColorOverride',
                {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}},
            )
        opt = {'format': format}
        if clip:
            opt['clip'] = clip
        result = await self._client.send('Page.captureScreenshot', opt)

        if options.get('omitBackground'):
            await self._client.send(
                'Emulation.setDefaultBackgroundColorOverride')

        if options.get('fullPage'):
            await self.setViewport(self._viewport)

        buffer = base64.b64decode(result.get('data', b''))
        _path = options.get('path')
        if _path:
            with open(_path, 'wb') as f:
                f.write(buffer)
        return buffer

    async def pdf(self, options: dict = None, **kwargs: Any) -> bytes:
        """Generate a pdf of the page.

        Options:

        * ``path`` (str): The file path to save the PDF.
        * ``scale`` (float): Scale of the webpage rendering, defaults to ``1``.
        * ``displayHeaderFooter`` (bool): Display header and footer.
          Defaults to ``False``.
        * ``headerTemplate`` (str): HTML template for the print header. Should
          be valid HTML markup with following classes.

          * ``data``: formatted print date
          * ``title``: document title
          * ``url``: document location
          * ``pageNumber``: current page number
          * ``totalPages``: total pages in the document

        * ``footerTemplate`` (str): HTML template for the print footer. Should
          use the same template as ``headerTemplate``.
        * ``printBackground`` (bool): Print background graphics. Defaults to
          ``False``.
        * ``landscape`` (bool): Paper orientation. Defaults to ``False``.
        * ``pageRanges`` (string): Paper ranges to print, e.g., '1-5,8,11-13'.
          Defaults to empty string, which means all pages.
        * ``foramt`` (str): Paper format. If set, takes prioprity over
          ``width`` or ``height``. Defaults to ``Letter``.
        * ``width`` (str): Paper width, accepts values labeled with units.
        * ``height`` (str): Paper height, accepts values labeled with units.
        * ``margin`` (dict): Paper margins, defaults to ``None``.

          * ``top`` (str): Top margin, accepts values labeled with units.
          * ``right`` (str): Right margin, accepts values labeled with units.
          * ``bottom`` (str): Bottom margin, accepts values labeled with units.
          * ``left`` (str): Left margin, accepts values labeled with units.

        :return bytes: Return generated PDF ``bytes`` object.
        """
        options = merge_dict(options, kwargs)
        scale = options.get('scale', 1)
        displayHeaderFooter = bool(options.get('displayHeaderFooter'))
        headerTemplate = options.get('headerTemplate', '')
        footerTemplate = options.get('footerTemplate', '')
        printBackground = bool(options.get('printBackground'))
        landscape = bool(options.get('landscape'))
        pageRanges = options.get('pageRanges', '')

        paperWidth = 8.5
        paperHeight = 11.0
        if 'format' in options:
            fmt = Page.PaperFormats.get(options['format'].lower())
            if not fmt:
                raise ValueError('Unknown paper format: ' + options['format'])
            paperWidth = fmt['width']
            paperHeight = fmt['height']
        else:
            paperWidth = convertPrintParameterToInches(options.get('width')) or paperWidth  # noqa: E501
            paperHeight = convertPrintParameterToInches(options.get('height')) or paperHeight  # noqa: E501

        marginOptions = options.get('margin', {})
        marginTop = convertPrintParameterToInches(marginOptions.get('top')) or 0  # noqa: E501
        marginLeft = convertPrintParameterToInches(marginOptions.get('left')) or 0  # noqa: E501
        marginBottom = convertPrintParameterToInches(marginOptions.get('bottom')) or 0  # noqa: E501
        marginRight = convertPrintParameterToInches(marginOptions.get('right')) or 0  # noqa: E501

        result = await self._client.send('Page.printToPDF', dict(
            landscape=landscape,
            displayHeaderFooter=displayHeaderFooter,
            headerTemplate=headerTemplate,
            footerTemplate=footerTemplate,
            printBackground=printBackground,
            scale=scale,
            paperWidth=paperWidth,
            paperHeight=paperHeight,
            marginTop=marginTop,
            marginBottom=marginBottom,
            marginLeft=marginLeft,
            marginRight=marginRight,
            pageRanges=pageRanges
        ))
        buffer = base64.b64decode(result.get('data', b''))
        if 'path' in options:
            with open(options['path'], 'wb') as f:
                f.write(buffer)
        return buffer

    async def plainText(self) -> str:
        """[Deprecated] Get page content as plain text."""
        logger.warning('`Page.plainText` is deprecated.')
        return await self.evaluate('() => document.body.innerText')

    async def title(self) -> str:
        """Get page title."""
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.title()

    async def close(self) -> None:
        """Close connection."""
        conn = self._client._connection
        if conn is None:
            raise PageError('Protocol Error: Connectoin Closed. '
                            'Most likely the page has been closed.')
        await conn.send('Target.closeTarget',
                        {'targetId': self._target._targetId})

    @property
    def mouse(self) -> Mouse:
        """Get :class:`~pyppeteer.input.Mouse` object."""
        return self._mouse

    async def click(self, selector: str, options: dict = None, **kwargs: Any
                    ) -> None:
        """Click element which matches ``selector``.

        This method fetches an element with ``selector``, scrolls it into view
        if needed, and then uses :attr:`mouse` to click in the center of the
        element. If there's no element matching ``selector``, the method raises
        ``PageError``.

        Available options are:

        * ``button`` (str): ``left``, ``right``, or ``middle``, defaults to
          ``left``.
        * ``clickCount`` (int): defaults to 1.
        * ``delay`` (int|float): Time to wait between ``mousedown`` and
          ``mouseup`` in milliseconds. defaults to 0.

        .. note:: If this method triggers a navigation event and there's a
            separate :meth:`waitForNavigation`, you may end up with a race
            condition that yields unexpected results. The correct pattern for
            click and wait for navigation is the following::

                await asyncio.wait([
                    page.waitForNavigation(waitOptions),
                    page.click(selector, clickOptions),
                ])
        """
        options = merge_dict(options, kwargs)
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.click(options)
        await handle.dispose()

    async def hover(self, selector: str) -> None:
        """Mouse hover the element which matches ``selector``.

        If no element matched the ``selector``, raise ``PageError``.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await handle.hover()
        await handle.dispose()

    async def focus(self, selector: str) -> None:
        """Focus the element which matches ``selector``.

        If no element matched the ``selector``, raise ``PageError``.
        """
        handle = await self.J(selector)
        if not handle:
            raise PageError('No node found for selector: ' + selector)
        await self.evaluate('element => element.focus()', handle)
        await handle.dispose()

    async def select(self, selector: str, *values: str) -> List[str]:
        """Select options and return selected values.

        If no element matched the ``selector``, raise ``ElementHandleError``.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return await frame.select(selector, *values)

    async def type(self, selector: str, text: str, options: dict = None,
                   **kwargs: Any) -> None:
        """Type ``text`` on the element which matches ``selector``.

        If no element matched the ``selector``, raise ``PageError``.

        Details see :meth:`pyppeteer.input.Keyboard.type`.
        """
        options = merge_dict(options, kwargs)
        handle = await self.querySelector(selector)
        if handle is None:
            raise PageError('Cannot find {} on this page'.format(selector))
        await handle.type(text, options)
        await handle.dispose()

    def waitFor(self, selectorOrFunctionOrTimeout: Union[str, int, float],
                options: dict = None, *args: Any, **kwargs: Any) -> Awaitable:
        """Wait for function, timeout, or element which matches on page.

        This method behaves differently with respect to the first argument:

        * If ``selectorOrFunctionOrTimeout`` is number (int or float), then it
          is treated as a timeout in milliseconds and this returns future which
          will be done after the timeout.
        * If ``selectorOrFunctionOrTimeout`` is a string of JavaScript
          function, this method is a shortcut to :meth:`waitForFunction`.
        * If ``selectorOrFunctionOrTimeout`` is a selector string, this method
          is a shortcut to :meth:`waitForSelector`.

        Pyppeteer tries to automatically detect function or selector, but
        sometimes miss-detects. If not work as you expected, use
        :meth:`waitForFunction` or :meth:`waitForSelector` dilectly.

        :arg selectorOrFunctionOrTimeout: A selector or
          function string, or timeout (milliseconds).
        :arg Any args: Arguments to pass the function.
        :return: Return awaitable object which resolves to a JSHandle of the
                 success value.

        Available options: see :meth:`waitForFunction` or
        :meth:`waitForSelector`
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return frame.waitFor(
            selectorOrFunctionOrTimeout, options, *args, **kwargs)

    def waitForSelector(self, selector: str, options: dict = None,
                        **kwargs: Any) -> Awaitable:
        """Wait until element which matches ``selector`` appears on page.

        Wait for the ``selector`` to appear in page. If at the moment of
        callingthe method the ``selector`` already exists, the method will
        return immediately. If the selector doesn't appear after the
        ``timeout`` milliseconds of waiting, the function will raise error.

        :arg str selector: A selector of an element to wait for.
        :return: Return awaitable object which resolves when element specified
                 by selector string is added to DOM.

        This method accepts the following options:

        * ``visible`` (bool): Wait for element to be present in DOM and to be
          visible; i.e. to not have ``display: none`` or ``visibility: hidden``
          CSS properties. Defaults to ``False``.
        * ``hidden`` (bool): Wait for eleemnt to not be found in the DOM or to
          be hidden, i.e. have ``display: none`` or ``visibility: hidden`` CSS
          properties. Defaults to ``False``.
        * ``timeout`` (int|float): Maximum time to wait for in milliseconds.
          Defaults to 30000 (30 seconds).
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return frame.waitForSelector(selector, options, **kwargs)

    def waitForFunction(self, pageFunction: str, options: dict = None,
                        *args: str, **kwargs: Any) -> Awaitable:
        """Wait until the function completes and returns a truethy value.

        :arg Any args: Arguments to pass to ``pageFunction``.
        :return: Return awaitable object which resolves when the
                 ``pageFunction`` returns a truethy value. It resolves to a
                 :class:`~pyppeteer.execution_context.JSHandle` of the truethy
                 value.

        This method accepts the following options:

        * ``polling`` (str|number): An interval at which the ``pageFunction``
          is executed, defaults to ``raf``. If ``polling`` is a number, then
          it is treated as an interval in milliseconds at which the function
          would be executed. If ``polling`` is a string, then it can be one of
          the following values:

          * ``raf``: to constantly execute ``pageFunction`` in
            ``requestAnimationFrame`` callback. This is the tightest polling
            mode which is suitable to observe styling changes.
          * ``mutation``: to execute ``pageFunction`` on every DOM mutation.

        * ``timeout`` (int|float): maximum time to wait for in milliseconds.
        """
        frame = self.mainFrame
        if not frame:
            raise PageError('no main frame.')
        return frame.waitForFunction(pageFunction, options, *args, **kwargs)


supportedMetrics = (
    'Timestamp',
    'Documents',
    'Frames',
    'JSEventListeners',
    'Nodes',
    'LayoutCount',
    'RecalcStyleCount',
    'LayoutDuration',
    'RecalcStyleDuration',
    'ScriptDuration',
    'TaskDuration',
    'JSHeapUsedSize',
    'JSHeapTotalSize',
)


unitToPixels = {
    'px': 1,
    'in': 96,
    'cm': 37.8,
    'mm': 3.78
}


def convertPrintParameterToInches(parameter: Union[None, int, float, str]
                                  ) -> Optional[float]:
    """Convert print parameter to inches."""
    if parameter is None:
        return None
    if isinstance(parameter, (int, float)):
        pixels = parameter
    elif isinstance(parameter, str):
        text = parameter
        unit = text[-2:].lower()
        if unit in unitToPixels:
            valueText = text[:-2]
        else:
            unit = 'px'
            valueText = text
        try:
            value = float(valueText)
        except ValueError:
            raise ValueError('Failed to parse parameter value: ' + text)
        pixels = value * unitToPixels[unit]
    else:
        raise TypeError('page.pdf() Cannot handle parameter type: ' +
                        str(type(parameter)))
    return pixels / 96


class ConsoleMessage(object):
    """Console message class.

    ConsoleMessage objects are dispatched by page via the ``console`` event.
    """

    def __init__(self, type: str, text: str, args: List[JSHandle]) -> None:
        #: (str) type of console message
        self._type = type
        #: (str) console message string
        self._text = text
        #: list of JSHandle
        self._args = args

    @property
    def type(self) -> str:
        """Return type of this message."""
        return self._type

    @property
    def text(self) -> str:
        """Return text representation of this message."""
        return self._text

    @property
    def args(self) -> List[JSHandle]:
        """Return list of args (JSHandle) of this message."""
        return self._args


#: alias to :func:`create_page()`
craete = Page.create
