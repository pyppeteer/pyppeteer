from asyncio import ensure_future
import asyncio
from time import perf_counter

def perf_counter_ms():
    return perf_counter()*1000

import pytest
from syncer import sync

from pyppeteer.errors import NetworkError, ElementHandleError, BrowserError


@sync
async def test_page_waitfor_selector_or_xpath(isolated_page, server):
    p = isolated_page
    # wait for selector
    await p.goto(server / 'grid.html')
    assert await p.waitFor('div')
    # wait for xpath
    assert await p.waitFor('//div')
    # should not work for for single-slash xpaths
    await p.setContent("""<div>some text</div>""")
    with pytest.raises(ElementHandleError):
        assert await p.waitFor('/div')


@sync
async def test_waitfor_multiline_body(isolated_page, server):
    p = isolated_page
    result = await p.waitForFunction("(() => true)()")
    assert await result.jsonValue()


@sync
async def test_waitfor_predicate(isolated_page, server):
    p = isolated_page
    await asyncio.gather(
        p.waitFor('() => window.innerWidth < 100'),
        p.setViewport({'width': 10, 'height': 10})
    )
    # with args
    await p.waitFor("(arg1, arg2) => arg1 !== arg2", "{}", 1, 2)


@sync
async def test_waitfor_unknown(isolated_page, server):
    p = isolated_page
    with pytest.raises(BrowserError, match='Unsupported target type'):
        await p.waitFor({'foo': 'bar'})


@sync
async def test_waitfor_function(isolated_page, server):
    p = isolated_page
    # should work with string functions
    watchdog = p.waitForFunction('window.__FOO === 1')
    await p.evaluate('window.__FOO = 1')
    await watchdog


@sync
async def test_waitfor_function_newdoc(isolated_page, server):
    p = isolated_page
    # should work when resolved right before execution context disposal
    await p.evaluateOnNewDocument('() => window.__RELOADED = true')
    # evaluate on new document doesn't seem to trigger on window.location.reload()?
    # await p.reload()
    await p.waitForFunction("""
    () => {
        if (!window.__RELOADED){
            window.location.reload();
        }
        return true;
    }
    """)


@sync
async def test_waitfor_poll_on_interval(isolated_page, server):
    p = isolated_page
    start = perf_counter_ms()
    polling = 100
    success = False

    async def watchdog():
        await p.waitForFunction('window.__FOO === "hit"', polling=polling)
        nonlocal success
        success = True

    await p.evaluate("window.__FOO = 'hit'")
    await watchdog()
    assert perf_counter_ms() - start >= polling / 2


@sync
async def test_waitfor_timeout(isolated_page, server):
    p = isolated_page
    start = perf_counter_ms() 
    timeout = 42
    await p.waitFor(timeout)
    assert perf_counter_ms() - start > timeout/2
