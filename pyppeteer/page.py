#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import base64
import json
import math
import mimetypes
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from pyee import EventEmitter

from pyppeteer import helper
from pyppeteer.connection import Session
from pyppeteer.dialog import Dialog
from pyppeteer.emulation_manager import EmulationManager
from pyppeteer.frame_manager import FrameManager
from pyppeteer.input import Keyboard, Mouse
from pyppeteer.navigator_watcher import NavigatorWatcher
from pyppeteer.network_manager import NetworkManager, Response
from pyppeteer.tracing import Tracing

if TYPE_CHECKING:
    from pyppeteer.element_handle import ElementHandle  # noqa: F401
    from pyppeteer.frame_manager import Frame  # noqa: F401


class Page(EventEmitter):
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
    )

    def __init__(self, client: Session,
                 ignoreHTTPSErrors: bool = True,
                 screenshotTaskQueue: list = None,
                 ) -> None:
        super().__init__()
        self._client = client
        self._keyboard = Keyboard(client)
        self._mouse = Mouse(client, self._keyboard)
        self._frameManager = FrameManager(client, self._mouse)
        self._networkManager = NetworkManager(client)
        self._emulationManager = EmulationManager(client)
        self._tracing = Tracing(client)
        self._pageBindings: Dict[str, Callable] = dict()
        self._ignoreHTTPSErrors = ignoreHTTPSErrors

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
                      exception.exceptionDetails))
        client.on('Security.certificateError',
                  lambda event: self._onCertificateError(event))
        client.on('Inspector.targetCrashed',
                  lambda event: self._onTargetCrashed())

    def _onTargetCrashed(self, *args: Any, **kwargs: Any) -> None:
        self.emit('error', Exception('Page crashed!'))

    @property
    def mainFrame(self) -> 'Frame':
        return self._frameManager._mainFrame

    @property
    def keyboard(self) -> 'Keyboard':
        return self._keyboard

    @property
    def tracing(self) -> 'Tracing':
        return self._tracing

    @property
    def frames(self) -> List['Frame']:
        return list(self._frames.values())

    async def setRequestInterceptionEnabled(self, value: bool) -> None:
        return await self._networkManager.setRequestInterceptionEnabled(value)

    def _onCertificateError(self, event: Any) -> None:
        if not self._ignoreHTTPSErrors:
            return
        asyncio.ensure_future(
            self._client.send('Security.handleCertificateError', {
                'eventId': event.get('eventId'),
                'action': 'continue'
            })
        )

    async def J(self, selector: str) -> Optional['ElementHandle']:
        return await self.mainFrame.J(selector)

    async def addScriptTag(self, url: str):
        return self.mainFrame.addScriptTag(url)

    async def injectFile(self, filePath: str):
        return self.mainFrame.injectFile(filePath)

    async def exposeFunction(self, name: str,
                             puppeteerFunction: Optional[Callable] = None,
                             ) -> None:
        if self._pageBindings[name]:
            raise Exception(f'Failed to add page binding with name {name}: '
                            'window["{name}"] already exists!')
        self._pageBindings[name] = puppeteerFunction

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
        await self._client.send('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True
        })

    async def setExtraHTTPHeaders(self, headers: Dict[str, str]):
        return self._networkManager.setExtraHTTPHeaders(headers)

    async def setUserAgent(self, userAgent: str):
        return self._networkManager.setUserAgent(userAgent)

    def _handleException(self, exceptionDetails: Dict) -> None:
        message = helper.getExceptionMessage(exceptionDetails)
        self.emit(Page.Events.PageError, Exception(message))

    async def _onConsoleAPI(self, event: dict) -> None:
        if (event.get('type') == 'debug' and
                len(event.get('args')) and
                event.get('args')[0].get('value') == 'driver:page-binding'):
            obj = json.loads(event.get('args')[1].get('value'))
            name = obj.get('name')
            seq = obj.get('seq')
            args = obj.get('args')
            result = await self._pageBindings[name](*args)

            deliverResult = '''
function deliverResult(name, seq, result) {
  window[name]['callbacks'].get(seq)(result)
  window[name]['callbacks'].delete(seq)
}
            '''
            expression = helper.evaluationString(deliverResult, name, seq,
                                                 result)
            await self._client.send('Runtime.evaluate', {
                'expression': expression
            })
            return

        if not self.listenerCount(Page.Events.Console):
            for arg in event.get('args'):
                helper.releaseObject(self._client, arg)
            return

        _values = []
        for arg in event.get('args'):
            _values.append(asyncio.ensure_future(
                helper.serializeRemoteObject(self._client, arg)))
        values = await asyncio.gather(*_values)
        self.emit(Page.Events.Console, *values)

    def _onDialog(self, event: Any) -> None:
        dialogType = None
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
        return self.mainFrame.url

    async def setContent(self, html: str) -> None:
        func = '''
fucntion(html) {
  document.open();
  document.write(html);
  document.close();
}
'''
        await self.evaluate(func, html)

    async def goto(self, url: str, options: dict = None
                   ) -> Optional[Response]:
        watcher = NavigatorWatcher(self._client, self._ignoreHTTPSErrors,
                                   options)
        responses: Dict[str, Response] = dict()
        listener = helper.addEventListener(
            self._networkManager, NetworkManager.Events.Response,
            lambda response: responses.__setitem__(response.url, response)
        )
        result = asyncio.ensure_future(watcher.waitForNavigation())
        referrer = self._networkManager.extraHTTPHeaders().get('referer', '')

        try:
            await self._client.send('Page.navigate',
                                    dict(url=url, referrer=referrer))
        except Exception:
            watcher.cancel()
            raise
        await result
        helper.removeEventListeners([listener])

        if self._frameManager.isMainFrameLoadingFailed():
            raise Exception('Failed to navigate: ' + url)
        return responses.get(self.mainFrame.url)

    async def reload(self, options: dict = None) -> Response:
        if options is None:
            options = dict()
        await self._client.send('Page.reload')
        return await self.waitForNavigation(options)

    async def waitForNavigation(self, options: dict = None) -> Response:
        if options is None:
            options = dict()
        watcher = NavigatorWatcher(self._client, self._ignoreHTTPSErrors,
                                   options)
        responses: Dict[str, Response] = dict()
        listener = helper.addEventListener(
            self._networkManager,
            NetworkManager.Events.Response,
            lambda response: responses.__setitem__(
                response.url, response)
        )
        await watcher.waitForNavigation()
        helper.removeEventListeners([listener])
        return responses[self.mainFrame.url]

    async def goBack(self, options: dict = None) -> Optional[Response]:
        if options is None:
            options = dict()
        return await self._go(-1, options)

    async def goForward(self, options: dict = None) -> Optional[Response]:
        if options is None:
            options = dict()
        return await self._go(+1, options)

    async def _go(self, delta: int, options: dict) -> Optional[Response]:
        history = await (await self._client.send('Page.getNavigationHistory'))
        _count = history.get('currentIndex', 0) + delta
        entries = history.get('entries', [])
        if len(entries) < _count:
            return None
        entry = entries[_count]
        await self._client.send('Page.navigateToHistoryEntry', {
            'entryId': entry.get('id')
        })
        return await self.waitForNavigation(options)

    async def emulate(self, options: dict) -> None:
        await self.setViewport(options.get('viewport', {}))
        await self.setUserAgent(options.get('userAgent', {}))

    async def setViewport(self, viewport: dict) -> None:
        needsReload = await self._emulationManager.emulateViewport(
            self._client, viewport,
        )
        self._viewport = viewport
        if needsReload:
            await self.reload()

    @property
    def viewport(self) -> dict:
        return self._viewport

    async def evaluate(self, pageFunction: str, *args: str) -> Optional[dict]:
        frame = self._frameManager.mainFrame
        if frame is None:
            raise Exception('No main frame.')
        return await frame.evaluate(pageFunction, *args)

    async def evaluateOnNewDocument(self, pageFunction: str, *args: str
                                    ) -> None:
        source = helper.evaluationString(pageFunction, *args)
        await self._client.send('Page.addScriptToEvaluateOnNewDocument', {
            'source': source,
        })

    async def screenshot(self, options: dict = None) -> bytes:
        options = options or dict()
        screenshotType = None
        if options.get('path'):
            mimeType, _ = mimetypes.guess_type(options.get('path'))
        if mimeType == 'image/png':
            screenshotType = 'png'
        elif mimeType == 'image/jpeg':
            screenshotType = 'jpeg'
        else:
            raise Exception(f'Unsupported screenshot mime type: {mimeType}')
        if options.get('type'):
            screenshotType = options.get('type')
        if not screenshotType:
            screenshotType = 'png'
        return await self._screenshotTask(screenshotType, options)

    async def _screenshotTask(self, format: str, options: dict) -> bytes:  # noqa: C901,E501
        await self._client.send('Target.activateTarget', {
            'targetId': self._client.targetId,
        })
        clip = options.get('clip')
        if clip:
            clip['scale'] = 1

        if options.get('fullPage'):
            metrics = await(await self._client.send('Page.getLayoutMetrics'))
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
        result = await (await self._client.send('Page.captureScreenshot', opt))

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

    async def pdf(self, options: dict) -> None:
        raise NotImplementedError

    async def plainText(self) -> str:
        return await self.evaluate('() => document.body.innerText')

    async def title(self) -> str:
        return await self.mainFrame.title()

    async def close(self) -> None:
        await self._client.dispose()

    @property
    def mouse(self) -> Mouse:
        return self._mouse

    async def click(self, selector: str, options: dict = None) -> None:
        if options is None:
            options = dict()
        handle = await self.J(selector)
        if not handle:
            raise Exception('No node found for selector: ' + selector)
        await handle.click(options)
        await handle.dispose()

    async def hover(self, selector: str) -> None:
        handle = await self.J(selector)
        if not handle:
            raise Exception('No node found for selector: ' + selector)
        await handle.hover()
        await handle.dispose()

    async def focus(self, selector: str) -> None:
        handle = await self.J(selector)
        if not handle:
            raise Exception('No node found for selector: ' + selector)
        await handle.evaluate('element => element.focus()')
        await handle.dispose()


async def create_page(client: Session, ignoreHTTPSErrors: bool = False,
                      screenshotTaskQueue: list = None) -> Page:
    await client.send('Network.enable', {}),
    await client.send('Page.enable', {}),
    await client.send('Runtime.enable', {}),
    await client.send('Security.enable', {}),
    if ignoreHTTPSErrors:
        await client.send('Security.setOverrideCertificateErrors',
                          {'override': True})
    page = Page(client, ignoreHTTPSErrors, screenshotTaskQueue)
    await page.goto('about:blank')
    # await page.setViewport({'width': 800, 'height': 600})
    return page


#: alias to :func:`create_page()`
craete = create_page
