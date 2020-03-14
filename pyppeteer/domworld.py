import asyncio
from asyncio import Future
from typing import Any, List, Optional, Dict, Generator, Union, TYPE_CHECKING, Awaitable, Callable

from pyppeteer import helper
from pyppeteer.errors import BrowserError, PageError, NetworkError
from pyppeteer.lifecycle_watcher import LifecycleWatcher
from pyppeteer.timeout_settings import TimeoutSettings

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from pyppeteer.jshandle import JSHandle, ElementHandle
    from pyppeteer.frame_manager import Frame, FrameManager
    from pyppeteer.execution_context import ExecutionContext


async def readFileAsync(path, file):
    # TODO implement this
    pass


class DOMWorld(object):
    def __init__(
        self, frameManager: 'FrameManager', frame: 'Frame', timeoutSettings: TimeoutSettings,
    ):
        self._frameManager = frameManager
        self._frame = frame
        self._timeoutSettings = timeoutSettings
        self.loop = self._frameManager._client.loop

        self._documentFuture: Future['ElementHandle'] = None
        self._contextFuture: Future['ExecutionContext'] = None
        self._contextResolveCallback: Callable = None
        self._setContext()

        self._waitTasks = set()
        self._detached = False

        # Aliases for query methods:
        self.J = self.querySelector
        self.Jx = self.xpath
        self.Jeval = self.querySelectorEval
        self.JJ = self.querySelectorAll
        self.JJeval = self.querySelectorAllEval

    @property
    def frame(self):
        return self._frame

    def _setContext(self, context: Optional['ExecutionContext'] = None):
        if context:
            self._contextResolveCallback(context)
            self._contextResolveCallback = None
            for waitTask in self._waitTasks:
                waitTask.rerun()
        else:
            self._documentFuture = None
            self._contextFuture = self.loop.create_future()
            self._contextResolveCallback = lambda _: self._contextFuture.set_result(None)

    def _hasContext(self):
        return not self._contextResolveCallback

    def _detach(self):
        self._detached = True
        for task in self._waitTasks:
            task.terminate(BrowserError('waitForFunctions failed: frame got detached.'))

    @property
    def executionContext(self) -> Awaitable['ExecutionContext']:
        if self._detached:
            raise BrowserError(
                'Execution Context is not available in detached '
                f'frame: {self._frame.url} (are you trying to evaluate?)'
            )
        return self._contextFuture

    async def evaluateHandle(self, pageFunction: str, *args):
        context = await self.executionContext
        return context.evaluateHandle(pageFunction=pageFunction, *args)

    async def evaluate(self, pageFunction: str, *args):
        context = await self.executionContext
        return context.evaluate(pageFunction=pageFunction, *args)

    async def querySelector(self, selector: str):
        document = await self._document
        return await document.querySelector(selector)

    @property
    async def _document(self) -> 'ElementHandle':
        if self._documentFuture:
            return await self._documentFuture

        context = await self.executionContext
        document = await context.evaluateHandle('document')
        self._documentFuture.set_result(document.asElement())
        return await self._documentFuture

    async def xpath(self, expression):
        document = await self._document
        return await document.xpath(expression)

    async def querySelectorEval(self, selector: str, pageFunction: str, *args: Any) -> Any:
        document = await self._document
        return await document.querySelectorEval(selector, pageFunction, *args)

    async def querySelectorAll(self, selector: str) -> List['ElementHandle']:
        """Get all elements which matches `selector`.

        Details see :meth:`pyppeteer.page.Page.querySelectorAll`.
        """
        document = await self._document
        value = await document.querySelectorAll(selector)
        return value

    async def querySelectorAllEval(self, selector: str, pageFunction: str, *args: Any) -> Optional[Dict]:
        """Execute function on all elements which matches selector.

        Details see :meth:`pyppeteer.page.Page.querySelectorAllEval`.
        """
        document = await self._document
        value = await document.JJeval(selector, pageFunction, *args)
        return value

    @property
    async def content(self):
        return await self.evaluate(
            """
            () => {
              let retVal = '';
              if (document.doctype)
                retVal = new XMLSerializer().serializeToString(document.doctype);
              if (document.documentElement)
                retVal += document.documentElement.outerHTML;
              return retVal;
            }
            """
        )

    async def setContent(self, html, waitUntil=None, timeout=None):
        if timeout is None:
            timeout = self._timeoutSettings.navigationTimeout
        if waitUntil is None:
            waitUntil = ['load']
        await self.evaluate(
            """
            html => {
              document.open();
              document.write(html);
              document.close();
            }
            """,
            html,
        )
        watcher = LifecycleWatcher(
            frameManager=self._frameManager, frame=self._frame, waitUntil=waitUntil, timeout=timeout
        )
        error = await helper.future_race(watcher.timeoutOrTerminationFuture, watcher.lifecycleFuture)
        watcher.dispose()
        if error:
            raise error

    async def addScriptTag(self, url=None, path=None, content=None, type=''):
        addScriptUrl = """
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
        }
        """
        addScriptContent = """
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
        }
        """
        context = await self.executionContext
        if url:
            try:
                return await context.evaluateHandle(addScriptUrl)
            except Exception as e:
                raise BrowserError(f'Loading script from {url} failed: {e}')
        if path:
            contents = await readFileAsync(path, 'utf8')
            contents += '//# sourceURL' + path.replace('\n', '')
            f = context.evaluateHandle(addScriptContent, contents, type)
            return (await f).asElement()
        if content:
            f = context.evaluateHandle(addScriptContent, content, type)
            return (await f).asElement()
        raise BrowserError('provide an object with url, path or content property')

    async def addStyleTag(self, url=None, path=None, content=None):
        addStyleUrl = """
        async function addStyleUrl(url) {
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
        }
        """
        addStyleContent = """
        async function addStyleContent(content) {
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
        }
        """
        context = await self.executionContext
        if url:
            try:
                return (await context.evaluateHandle(addStyleUrl, url)).asElement()
            except Exception as e:
                raise BrowserError(f'Loading style from {url} failed')

        if path:
            contents = await readFileAsync(path, 'utf8')
            contents += '/*# sourceURL=' + path.replace('\n', '') + '*/'
            return (await context.evaluateHandle(addStyleContent, contents)).asElement()

        if content:
            return (await context.evaluateHandle(addStyleContent, content)).asElement()
        raise BrowserError('provide an object with url, path or content property')

    async def _select_handle(self, selector):
        handle = await self.querySelector(selector)
        if not handle:
            raise BrowserError(f'No node found for selector: {selector}')

    async def click(self, selector: str, button: Literal['left', 'right', 'middle'] = None, clickCount: int = None):
        """
        :param selector:
        :param kwargs:
        delay: number, button: "left"|"right"|"middle", clickCount: number
        :param kwargs:
        :return:
        """
        handle = await self._select_handle(selector)
        await handle.click(button=button, clickCount=clickCount)
        await handle.dispose()

    async def focus(self, selector: str):
        handle = await self._select_handle(selector)
        await handle.focus()
        await handle.dispose()

    async def hover(self, selector: str):
        handle = await self._select_handle(selector)
        await handle.hover()
        await handle.dispose()

    async def select(self, selector: str, *values):
        handle = await self._select_handle(selector)
        result = await handle.select(*values)
        await handle.dispose()
        return result

    async def tap(self, selector: str):
        handle = await self._select_handle(selector)
        await handle.tap()
        await handle.dispose()

    async def type(self, selector: str, text: str, **kwargs):
        handle = await self._select_handle(selector)
        await handle.type(text, **kwargs)
        await handle.dispose()

    async def waitForSelector(self, selector, visible=False, hidden=False, timeout: int = None):
        return self._waitForSelectorOrXpath(selector, isXPath=False, visible=visible, hidden=hidden, timeout=timeout)

    async def waitForXpath(self, xpath, visible=False, hidden=False, timeout: int = None):
        return self._waitForSelectorOrXpath(xpath, isXPath=True, visible=visible, hidden=hidden, timeout=timeout)

    async def waitForFunction(self, pageFunction, polling='raf', timeout=None, *args):
        if not timeout:
            timeout = self._timeoutSettings.timeout
        return WaitTask(self, pageFunction, 'function', polling, timeout, *args).promise

    @property
    async def title(self):
        return self.evaluate('() => document.title')

    async def _waitForSelectorOrXpath(self, selectorOrXpath, isXPath, visible=False, hidden=False, timeout=None):
        if not timeout:
            timeout = self._timeoutSettings.timeout
        if visible or hidden:
            polling = 'raf'
        else:
            polling = 'mutation'
        title = f"{'XPath' if isXPath else 'selector'} " f"{selectorOrXpath}" f"{' to be hidden' if hidden else ''}"
        predicate = """
        function predicate(selectorOrXPath, isXPath, waitForVisible, waitForHidden) {
          const node = isXPath
            ? document.evaluate(selectorOrXPath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue
            : document.querySelector(selectorOrXPath);
          if (!node)
            return waitForHidden;
          if (!waitForVisible && !waitForHidden)
            return node;
          const element = /** @type {Element} */ (node.nodeType === Node.TEXT_NODE ? node.parentElement : node);

          const style = window.getComputedStyle(element);
          const isVisible = style && style.visibility !== 'hidden' && hasVisibleBoundingBox();
          const success = (waitForVisible === isVisible || waitForHidden === !isVisible);
          return success ? node : null;

          /**
           * @return {boolean}
           */
          function hasVisibleBoundingBox() {
            const rect = element.getBoundingClientRect();
            return !!(rect.top || rect.bottom || rect.width || rect.height);
          }
        }
        """
        waitTask = WaitTask(self, predicate, title, polling, timeout, selectorOrXpath, isXPath, visible, hidden)
        handle = await waitTask.promise
        if not handle.asElement():
            await handle.dispose()
            return None
        return handle.asElement()


class WaitTask(object):
    """WaitTask class.

    Instance of this class is awaitable.
    """

    def __init__(
        self,
        domWorld: DOMWorld,
        predicateBody: str,
        title: str,
        polling: Union[str, int],
        timeout: float,
        loop: asyncio.AbstractEventLoop,
        *args: Any,
    ) -> None:
        if isinstance(polling, str):
            if polling not in ['raf', 'mutation']:
                raise ValueError(f'Unknown polling: {polling}')
        elif isinstance(polling, (int, float)):
            if polling <= 0:
                raise ValueError(f'Cannot poll with non-positive interval: {polling}')
        else:
            raise ValueError(f'Unknown polling option: {polling}')

        self._domWorld = domWorld
        self._polling = polling
        self._timeout = timeout
        self.loop = loop
        if args or helper.is_jsfunc(predicateBody):
            self._predicateBody = f'return ({predicateBody})(...args)'
        else:
            self._predicateBody = f'return {predicateBody}'
        self._args = args
        self._runCount = 0
        self._terminated = False
        self._timeoutError = False
        domWorld._waitTasks.add(self)

        self.promise = self.loop.create_future()

        async def timer(timeout: float) -> None:
            await asyncio.sleep(timeout / 1000)
            self._timeoutError = True
            self.terminate(TimeoutError(f'Waiting for {title} failed: timeout {timeout}ms exceeds.'))

        if timeout:
            self._timeoutTimer = self.loop.create_task(timer(self._timeout))
        self._runningTask = self.loop.create_task(self.rerun())

    def __await__(self) -> Generator:
        """Make this class **awaitable**."""
        result = yield from self.promise
        if isinstance(result, Exception):
            raise result
        return result

    def terminate(self, error: Exception) -> None:
        """Terminate this task."""
        self._terminated = True
        if not self.promise.done():
            self.promise.set_exception(error)
        self._cleanup()

    async def rerun(self) -> None:  # noqa: C901
        """Start polling."""
        runCount = self._runCount = self._runCount + 1
        success: Optional['JSHandle'] = None
        error = None

        try:
            context = await self._domWorld.executionContext
            if context is None:
                raise PageError('No execution context.')
            success = await context.evaluateHandle(
                waitForPredicatePageFunction, self._predicateBody, self._polling, self._timeout, *self._args,
            )
        except Exception as e:
            error = e

        if self.promise.done():
            return

        if self._terminated or runCount != self._runCount:
            if success:
                await success.dispose()
            return

        # Add try/except referring to puppeteer.
        try:
            if not error and success and (await self._domWorld.evaluate('s => !s', success)):
                await success.dispose()
                return
        except NetworkError:
            if success is not None:
                await success.dispose()
            return

        # page is navigated and context is destroyed.
        # Try again in the new execution context.
        if isinstance(error, NetworkError) and 'Execution context was destroyed' in error.args[0]:
            return

        # Try again in the new execution context.
        if isinstance(error, NetworkError) and 'Cannot find context with specified id' in error.args[0]:
            return

        if error:
            self.promise.set_exception(error)
        else:
            self.promise.set_result(success)

        self._cleanup()

    def _cleanup(self) -> None:
        if self._timeout and not self._timeoutError:
            self._timeoutTimer.cancel()
        self._domWorld._waitTasks.remove(self)
        self._runningTask = None


waitForPredicatePageFunction = """
async function waitForPredicatePageFunction(predicateBody, polling, timeout, ...args) {
  const predicate = new Function('...args', predicateBody);
  let timedOut = false;
  if (timeout)
    setTimeout(() => timedOut = true, timeout);
  if (polling === 'raf')
    return await pollRaf();
  if (polling === 'mutation')
    return await pollMutation();
  if (typeof polling === 'number')
    return await pollInterval(polling);

  /**
   * @return {!Promise<*>}
   */
  function pollMutation() {
    const success = predicate.apply(null, args);
    if (success)
      return Promise.resolve(success);

    let fulfill;
    const result = new Promise(x => fulfill = x);
    const observer = new MutationObserver(mutations => {
      if (timedOut) {
        observer.disconnect();
        fulfill();
      }
      const success = predicate.apply(null, args);
      if (success) {
        observer.disconnect();
        fulfill(success);
      }
    });
    observer.observe(document, {
      childList: true,
      subtree: true,
      attributes: true
    });
    return result;
  }

  /**
   * @return {!Promise<*>}
   */
  function pollRaf() {
    let fulfill;
    const result = new Promise(x => fulfill = x);
    onRaf();
    return result;

    function onRaf() {
      if (timedOut) {
        fulfill();
        return;
      }
      const success = predicate.apply(null, args);
      if (success)
        fulfill(success);
      else
        requestAnimationFrame(onRaf);
    }
  }

  /**
   * @param {number} pollInterval
   * @return {!Promise<*>}
   */
  function pollInterval(pollInterval) {
    let fulfill;
    const result = new Promise(x => fulfill = x);
    onTimeout();
    return result;

    function onTimeout() {
      if (timedOut) {
        fulfill();
        return;
      }
      const success = predicate.apply(null, args);
      if (success)
        fulfill(success);
      else
        setTimeout(onTimeout, pollInterval);
    }
  }
}
"""
