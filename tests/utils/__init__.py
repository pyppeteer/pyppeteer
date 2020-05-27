import asyncio
import ctypes
import inspect
import random
from asyncio.futures import Future
from asyncio.tasks import Task
from typing import Any, Awaitable, List, Optional, Union

from pyppeteer.frame import Frame
from pyppeteer.page import Page


async def attachFrame(page: Page, url: str, frameId: str = None):
    if frameId is None:
        frameId = f'frame_autogen_name_{random.randint(100000,999999)}'
    attach_frame_js = '''
    async function attachFrame(frameId, url) {
      const frame = document.createElement('iframe');
      frame.src = url;
      frame.id = frameId;
      document.body.appendChild(frame);
      await new Promise(x => frame.onload = x);
      return frame;
    }
    '''
    handle = await page.evaluateHandle(attach_frame_js, frameId, url)
    return await handle.asElement().contentFrame()


def waitEvent(emitter, event_name: str) -> Awaitable[Any]:
    """
    Returns a future which resolves to the event's details when event_name is emitted from emitter
    :param emitter: emitter to attach callback to
    :param event_name: name of event to trigger callback
    :return: Awaitable[Any]
    """
    fut = asyncio.get_event_loop().create_future()

    def set_done(arg=None):
        fut.set_result(arg)

    emitter.once(event_name, set_done)
    return fut


def gather_with_timeout(
    *aws: Awaitable, timeout: Optional[float] = 2.5, **kwargs
) -> Awaitable[List[Union[Task, Future]]]:
    """
    Similar to asyncio.gather, but with one key difference: It will timeout. A wrapped asyncio.gather approach was
    chosen over asyncio.wait or asyncio.wait_for, etc. because asyncio.gather returns the awaitables in the same order
    that they were passed in, which allows for closer analogous behaviour to JS's Promise.all
    :param aws: Awaitables to gather
    :param timeout: amount of time to wait, in seconds, before raising timeout error
    :param kwargs: kwargs to pass to asyncio.gather
    :return: same as asyncio.gather
    """
    return asyncio.wait_for(asyncio.gather(*aws, **kwargs), timeout=timeout)


async def detachFrame(page: Page, frameId: str) -> None:
    func = '''
        (frameId) => {
            const frame = document.getElementById(frameId);
            frame.remove();
        }
    '''
    await page.evaluate(func, frameId)


async def navigateFrame(page: Page, frameId: str, url: str) -> None:
    func = '''
        (frameId, url) => {
            const frame = document.getElementById(frameId);
            frame.src = url;
            return new Promise(x => frame.onload = x);
        }
    '''
    await page.evaluate(func, frameId, url)


def dumpFrames(frame: Frame, indentation: str = '') -> List[str]:
    description = frame.url
    if frame.name:
        description += f' ({frame.name})'
    results = [indentation + description]
    for child in frame.childFrames:
        results.extend(dumpFrames(child, '    ' + indentation))
    return results


def isFavicon(req) -> bool:
    return 'favicon.ico' in req.url


def var_setter(name, default_value=None):
    """
    Returns a function which takes one argument, value. The function returned takes one arg, value, and sets the
    variable in the locals of the caller's frame with the name of name to (value or default_value).

    Args:
        name: name of value in callers locals to set
        default_value: value to set variable too on calling the returned function

    Returns: Callable
        function taking one arg to set variable with the name of name in callers locals
    """
    stack_frame = inspect.stack()[1][0]

    def _setter_func(value=default_value):
        stack_frame.f_locals[name] = value
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(stack_frame), ctypes.c_int(0))

    return _setter_func
