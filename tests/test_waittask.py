from asyncio import ensure_future
import asyncio
from time import perf_counter

from tests.utils import attachFrame, detachFrame


def perf_counter_ms():
    return perf_counter() * 1000


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
    """should work when resolved right before execution context disposal"""
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
    """should poll on interval"""
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
async def test_poll_on_mutation(isolated_page, server):
    """should poll on mutation"""
    p = isolated_page
    success = False

    async def watchdog():
        await p.waitForFunction('window.__FOO === "hit"', polling='mutation')
        nonlocal success
        success = True

    await p.evaluate("window.__FOO = 'hit'")
    assert success is False
    await p.evaluate("document.body.appendChild(document.createElement('div'))")
    await watchdog()
    assert success is True


@sync
async def test_poll_on_raf(isolated_page, server):
    """should poll on raf"""
    p = isolated_page
    success = False

    async def watchdog():
        await p.waitForFunction('window.__FOO === "hit"', polling='raf')
        nonlocal success
        success = True

    await p.evaluate("window.__FOO = 'hit'")
    assert success is False
    await watchdog()
    assert success is True


@sync
async def test_work_with_strict_CSP_policy(isolated_page, server):
    """should work with strict CSP policy"""
    p = isolated_page
    server.setCSP('/empty.html', 'script-src ' + server.prefix)
    # todo


@sync
async def test_bad_polling_value(isolated_page, server):
    """should throw on bad polling value"""
    p = isolated_page
    with pytest.raises(ValueError, match='polling'):
        await p.waitForFunction('() => !!document.body', polling='unknown')


@sync
async def test_negative_polling_value(isolated_page, server):
    p = isolated_page
    with pytest.raises(ValueError, match='Cannot poll with non-positive interval'):
        await p.waitForFunction('() => !!document.body', polling=-1)


@sync
async def test_success_value_as_jshandle(isolated_page, server):
    """should return success value as a JSHandle"""
    p = isolated_page
    assert await (await p.waitForFunction('() => 5')).jsonValue() == 5


@sync
async def test_success_value_as_window(isolated_page, server):
    """should return the window as a success value"""
    p = isolated_page
    assert await p.waitForFunction('() => window')


@sync
async def test_accept_elementhandle_args(isolated_page, server):
    """should accept ElementHandle arguments"""
    p = isolated_page
    await p.setContent('<div></div>')
    div = await p.J('div')
    resolved = False

    async def waitForFunction():
        element = await p.waitForFunction(
            'element => !element.parentElement', div
        )
        nonlocal resolved
        resolved = True

    assert resolved is False
    p.evaluate('element => element.remove', div)
    await waitForFunction()
    assert resolved is True


@sync
async def test_respect_timeout(isolated_page, server):
    """should respect timeout"""
    p = isolated_page
    # TODO this doesn't raise error
    with pytest.raises(BrowserError, match='waiting for function failed: timeout'):
        await p.waitForFunction('false', timeout=10_000)


@sync
async def test_disable_timeout(isolated_page, server):
    p = isolated_page

    async def watchdog():
        await p.waitForFunction("""
            () => {
            window.__counter = (window.__counter || 0) + 1;
            return window.__injected;}
            """, timeout=0, polling=10)

    await p.waitForFunction('window.__counter > 10')
    await p.evaluate('window.__injected = true')
    await watchdog()


@sync
async def test_survive_cross_process_nav(isolated_page, server):
    """should survive cross-process navigation"""
    p = isolated_page
    fooFound = False

    async def waitForFunction():
        await p.waitForFunction('window.__FOO === 1')
        nonlocal fooFound
        fooFound = True

    await p.goto(server.empty_page)
    assert fooFound is False
    await p.reload()
    assert fooFound is False
    await p.evaluate('window.__FOO = 1')
    await waitForFunction()
    assert fooFound is True


async def add_element(frame, tag):
    await frame.evaluate(
        """tag => document.body.appendChild(document.createElement(tag))""",
        tag
    )


@sync
async def test_resolve_promise(isolated_page, server):
    """should immediately resolve promise if node exists"""
    p = isolated_page
    await p.goto(server.empty_page)
    frame = p.mainFrame
    await frame.waitForSelector('*')
    await add_element(frame, 'div')
    await frame.waitForSelector('div')


@sync
async def test_remove_mutation_observer(isolated_page, server):
    """should work with removed MutationObserver"""
    p = isolated_page
    handle = await asyncio.gather(
        p.waitForSelector('.zombo'),
        p.setContent('<div class="zombo">anything</div>'),
    )
    # TODO this doesn't work
    assert await p.evaluate('x => x.textContent', handle) == 'anything'


@sync
async def test_resolve_on_node_add(isolated_page, server):
    """should resolve promise when node is added"""
    p = isolated_page
    await p.goto(server.empty_page)
    frame = p.mainFrame
    watchdog = frame.waitForSelector('div')
    await add_element(frame, 'br')
    await add_element(frame, 'div')
    eHandle = await watchdog
    tagName = await eHandle.getProperty('tagName')
    assert await tagName.jsonValue() == 'DIV'


@sync
async def test_node_added_through_innerhtml(isolated_page, server):
    p = isolated_page
    await p.goto(server.empty_page)
    watchdog = p.waitForSelector('h3  div')
    await add_element(p.mainFrame, 'span')
    await p.evaluate('document.querySelector("span").innerHTML = "<h3><div></div></h3>"')
    await watchdog


@sync
async def test_page_mainframe_shortcut(isolated_page, server):
    """Page.waitForSelector is shortcut for main frame"""
    p = isolated_page
    await p.goto(server.empty_page)
    await attachFrame(p, server.empty_page, 'frame1')
    otherFrame = p.frames[1]
    watchdog = p.waitForSelector('div')
    await add_element(otherFrame, 'div')
    await add_element(p, 'div')
    eHandle = await watchdog
    assert eHandle.executionContext.frame is p.mainFrame


@sync
async def test_run_in_specified_frame(isolated_page, server):
    """should run in specified frame"""
    p = isolated_page
    await attachFrame(p, server.empty_page, 'frame1')
    await attachFrame(p, server.empty_page, 'frame2')
    frame1 = p.frames[1]
    frame2 = p.frames[2]
    waitForSelectorPromise = frame2.waitForSelector('div')
    await add_element(frame1, 'div')
    await add_element(frame2, 'div')
    eHandle = await waitForSelectorPromise
    assert eHandle.executionContext.frame is frame2


@sync
async def test_throw_when_frame_is_detached(isolated_page, server):
    """should throw when frame is detached"""
    p = isolated_page
    await attachFrame(p, server.empty_page, 'frame1')
    frame = p.frames[1]
    waitPromise = frame.waitForSelector('.box')
    await detachFrame(p, 'frame1')
    with pytest.raises(BrowserError):
        await waitPromise


@sync
async def test_selector_survive_cross_process_navigation(isolated_page, server):
    """should survive cross-process navigation"""
    p = isolated_page
    boxFound = False

    async def waitForSelector():
        await p.waitForSelector('.box')
        nonlocal boxFound
        boxFound = True

    await p.goto(server.empty_page)
    assert boxFound is False
    await p.reload()
    assert boxFound is False
    await p.goto(server.cross_process_server / '/grid.html')
    await waitForSelector()
    assert boxFound is True


@sync
async def test_wait_for_visible(isolated_page, server):
    """should wait for visable"""
    p = isolated_page
    divFound = False

    async def waitForSelector():
        elem = p.waitForSelector('div', visible=True)
        nonlocal divFound
        divFound = True
        return elem

    await p.setContent("<div style='display: none; visibility: hidden;'>1</div>")
    assert divFound is False
    await p.evaluate('document.querySelector("div").style.removeProperty("display")')
    assert divFound is False
    await p.evaluate('document.querySelector("div").style.removeProperty("visibility")')
    assert await waitForSelector()
    assert divFound is True


@sync
async def test_wait_for_visible_recursively(isolated_page, server):
    """should wait for visible recursively"""
    p = isolated_page
    divVisible = False

    async def waitForSelector():
        elem = await p.waitForSelector('div#inner', visible=True)
        nonlocal divVisible
        divVisible = True
        return elem

    await p.setContent("""<div style='display: none; visibility: hidden;'><div id="inner">hi</div></div>""")
    assert divVisible is False
    await p.evaluate("document.querySelector('div').style.removeProperty('display')")
    assert divVisible is False
    await p.evaluate("document.querySelector('div').style.removeProperty('visibility')")
    assert await waitForSelector()
    assert divVisible is True


@sync
async def test_hidden_should_wait_for_visibility_hidden(isolated_page, server):
    """hidden should wait for visibility: hidden"""
    p = isolated_page
    await p.setContent("<div style='display: block;'></div>")
    divHidden = False

    async def waitForSelector():
        elem = await p.waitForSelector('div', hidden=True)
        nonlocal divHidden
        divHidden = True
        return elem

    await p.waitForSelector('div')
    assert divHidden is False
    await p.evaluate("() => document.querySelector('div').style.setProperty('visibility', 'hidden')")
    assert await waitForSelector()
    assert divHidden is True


@sync
async def test_wait_for_display_none(isolated_page, server):
    """hidden should wait for display: none"""
    p = isolated_page
    await p.setContent("<div style='display: block;'></div>")
    divHidden = False

    async def waitForSelector():
        elem = await p.waitForSelector('div', hidden=True)
        nonlocal divHidden
        divHidden = True
        return elem

    await p.waitForSelector('div')
    assert divHidden is False
    await p.evaluate("document.querySelector('div').style.setProperty('display', 'none')")
    assert await waitForSelector()
    assert divHidden is True


@sync
async def test_hidden_wait_for_removal(isolated_page, server):
    """hidden should wait for removal"""
    p = isolated_page
    await p.setContent('<div></div>')
    divRemoved = False

    async def waitForSelector():
        elem = await p.waitForSelector('div', hidden=True)
        nonlocal divRemoved
        divRemoved = True
        return elem

    await p.waitForSelector('div')
    assert divRemoved is False
    await p.evaluate("document.querySelector('div').remove()")
    assert await waitForSelector() is None
    assert divRemoved is True


@sync
async def test_null_if_waiting_to_hide_nothing(isolated_page, server):
    """should return null if waiting to hide non-existing element"""
    p = isolated_page
    handle = await p.waitForSelector('non-existing', hidden=True)
    assert handle is None


@sync
async def test_waitforselector_respect_timeout(isolated_page, server):
    """should respect timeout"""
    p = isolated_page
    with pytest.raises(TimeoutError, match='Waiting for selector div failed: timeout of'):
        await p.waitForSelector('div', timeout=10)


@sync
async def test_error_for_awaiting_hidden_elem(isolated_page, server):
    """should have an error message specifically for awaiting an element to be hidden"""
    p = isolated_page
    await p.setContent('<div></div>')
    with pytest.raises(TimeoutError, match='Waiting for selector div to be hidden failed: timeout of 10ms exceeded'):
        await p.waitForSelector('div', hidden=True, timeout=10)


@sync
async def test_respond_to_node_attribute_mutation(isolated_page, server):
    """should respond to node attribute mutation"""
    p = isolated_page
    divFound = False

    async def waitForSelector():
        elem = await p.waitForSelector('.zombo')
        nonlocal divFound
        divFound = True
        return elem

    await p.setContent('<div class="notZombo"></div>')
    assert divFound is False
    await p.evaluate("document.querySelector('div').className = 'zombo'")
    assert await waitForSelector()
    assert divFound is True


@sync
async def test_return_elem_handle(isolated_page, server):
    """should return element handle"""
    p = isolated_page

    waitForSelector = p.waitForSelector('.zombo')
    await p.setContent("<div class='zombo'>anything</div>")
    assert await p.evaluate('x => x.textContent', await waitForSelector) == 'anything'


@sync
async def test_correct_stack_for_timeout(isolated_page, server):
    """should have correct stack trace for timeout"""
    # todo this test wants to check stacktrace
    p = isolated_page

    with pytest.raises(TimeoutError):
        await p.waitForSelector('.zombo', timeout=10)


@sync
async def test_fancy_xpath(isolated_page, server):
    p = isolated_page
    await p.setContent('<p>red herring</p><p>hello  world  </p>')
    waitForXpath = p.waitForXpath('//p[normalize-space(.)="hello world"]')
    result = await p.evaluate(
        'x => x.textContent, await waitForXpath',
        {'waitForXpath': waitForXpath})
    assert result == 'hello  world  '



@sync
async def test_waitfor_timeout(isolated_page, server):
    """should respect timeout"""
    p = isolated_page
    start = perf_counter_ms()
    timeout = 42
    await p.waitFor(timeout)
    assert perf_counter_ms() - start > timeout / 2
