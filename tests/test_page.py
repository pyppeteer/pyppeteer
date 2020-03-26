import asyncio
from contextlib import suppress
from typing import Optional, List

import pytest
from syncer import sync

from pyppeteer import devices
from pyppeteer.errors import TimeoutError, ElementHandleError, NetworkError, BrowserError
from pyppeteer.page import ConsoleMessage
from tests.utils import waitEvent, gather_with_timeout, attachFrame


@sync
async def test_async_stacks(isolated_page, server):
    with pytest.raises(Exception) as excpt:
        await isolated_page.goto(server.empty_page)
        assert __file__ in str(excpt)


class TestClose:
    @sync
    async def test_reject_all_pending_promises(self, isolated_page, event_loop):
        fut = event_loop.create_task(isolated_page.evaluate('()=>new Promise(resolve=>{})'))
        await isolated_page.close()
        with pytest.raises(Exception) as excpt:
            await fut
        assert 'Protocol error' in str(excpt)

    @sync
    async def test_closed_page_removed_from_pages_prop(self, isolated_page, shared_browser):
        assert isolated_page in await shared_browser.pages
        await isolated_page.close()
        assert isolated_page not in await shared_browser.pages

    @sync
    async def test_run_beforeunload(self, isolated_page, server, firefox):
        await isolated_page.goto(server / 'beforeunload.html')
        # interact w/ page so beforeunload handler fires
        await isolated_page.click('body')
        page_closing_fut = isolated_page._loop.create_task(isolated_page.close(runBeforeUnload=True))
        dialog = await waitEvent(isolated_page, 'dialog')
        assert dialog.type == 'beforeunload'
        assert dialog.defaultValue == ''
        if not firefox:
            assert dialog.message == ''
        elif firefox:
            assert (
                dialog.message
                == 'This page is asking you to confirm that you want to leave - data you have entered may not be saved.'
            )
        await dialog.accept()
        await page_closing_fut

    @sync
    async def test_not_run_beforeunload_by_default(self, isolated_page, server):
        await isolated_page.goto(server / 'beforeunload.html')
        # interact w/ page so beforeunload handler fires
        await isolated_page.click('body')
        # if beforeunload handlers are fired, this will timeout as a dialog will block the close of the page
        await isolated_page.close()

    @sync
    async def test_set_page_close_state(self, isolated_page, server):
        assert isolated_page.isClosed is False
        await isolated_page.close()
        assert isolated_page.isClosed


class TestEventsLoad:
    @sync
    async def test_load_event_fired(self, isolated_page):
        event = waitEvent(isolated_page, 'load')
        done, _ = await asyncio.wait((isolated_page.goto('about:blank'), event), timeout=5)
        assert len(done) == 2


class TestEventError:
    @sync
    async def test_raises_on_page_crash(self, event_loop, isolated_page):
        error = waitEvent(isolated_page, 'error')
        with suppress(asyncio.TimeoutError):
            await isolated_page.goto('chrome://crash', timeout=2_000)
        assert str(await error) == 'Page crashed!'


class TestEventsPopup:
    @sync
    async def test_popup_props(self, isolated_page):
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'), isolated_page.evaluate('() => window.open("about:blank")'),
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener')

    @sync
    async def test_popup_noopener(self, isolated_page):
        popup, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'popup'),
            isolated_page.evaluate('() => window.open("about:blank", null, "noopener")'),
        )
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False

    @sync
    async def test_clicking_target_blank(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.setContent('<a target=_blank href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(waitEvent(isolated_page, 'popup'), isolated_page.click('a'),)
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener')

    @sync
    async def test_fake_clicking_target_and_noopener(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.setContent('<a target=_blank rel=noopener href="/one-style.html">yo</a>')
        popup, *_ = await gather_with_timeout(waitEvent(isolated_page, 'popup'), isolated_page.click('a'))
        assert await isolated_page.evaluate('() => !!window.opener') is False
        assert await popup.evaluate('() => !!window.opener') is False


class TestBrowserContextOverridePermissions:
    @staticmethod
    def get_permission_state(page, name):
        return page.evaluate('name => navigator.permissions.query({name}).then(result => result.state)', name)

    @sync
    async def test_prompt_by_default(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'prompt'

    @sync
    async def test_deny_unlisted_permission(self, isolated_page, isolated_context, server):
        await isolated_page.goto(server.empty_page)
        await isolated_context.overridePermissions(server.empty_page, [])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'denied'

    @sync
    async def test_fail_on_bad_permission(self, isolated_page, isolated_context, server):
        await isolated_page.goto(server.empty_page)
        with pytest.raises(RuntimeError) as excpt:
            await isolated_context.overridePermissions(server.empty_page, ['foo'])
        assert 'Unknown permission: foo' in str(excpt)

    @sync
    async def test_grant_permission_when_overridden(self, isolated_page, isolated_context, server):
        await isolated_context.overridePermissions(server.empty_page, ['geolocation'])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'granted'

    @sync
    async def test_reset_permissions(self, isolated_page, isolated_context, server):
        await isolated_context.overridePermissions(server.empty_page, ['geolocation'])
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'granted'
        await isolated_context.clearPermissionOverrides()
        assert await self.get_permission_state(isolated_page, 'geolocation') == 'prompt'

    @sync
    async def test_permission_onchange_fired(self, isolated_page, isolated_context, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate(
            """
        () => {
            window.events = [];
            return navigator.permissions.query({name: 'geolocation'}).then(function(result) {
                window.events.push(result.state);
                result.onchange = function() {
                    window.events.push(result.state);
                };
            });
        }
        """
        )
        assert await isolated_page.evaluate('() => window.events') == ['prompt']
        await isolated_context.overridePermissions(server.empty_page, [])
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied']
        await isolated_context.overridePermissions(server.empty_page, ['geolocation'])
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied', 'granted']
        await isolated_context.clearPermissionOverrides()
        assert await isolated_page.evaluate('() => window.events') == ['prompt', 'denied', 'granted', 'prompt']


class TestSetGeolocation:
    @sync
    async def test_set_geolocation(self, isolated_page, isolated_context, server):
        await isolated_context.overridePermissions(server.empty_page, ['geolocation'])
        await isolated_page.goto(server.empty_page)
        await isolated_page.setGeolocation(longitude=10, latitude=10)
        geolocation = await isolated_page.evaluate(
            """
        () => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
            resolve({latitude: position.coords.latitude, longitude: position.coords.longitude});
        }))
        """
        )
        assert geolocation == {'longitude': 10, 'latitude': 10}

    @sync
    async def test_rejects_invalid_lat_long(self, isolated_page):
        with pytest.raises(NetworkError):
            await isolated_page.setGeolocation(longitude=200, latitude=10)
        with pytest.raises(NetworkError):
            await isolated_page.setGeolocation(longitude=90, latitude=200)


class TestSetOfflineMode:
    @sync
    async def test_set_offline_mode(self, isolated_page, server):
        await isolated_page.setOfflineMode(True)
        with pytest.raises(BrowserError):
            await isolated_page.goto(server.empty_page)
        await isolated_page.setOfflineMode(False)
        resp = await isolated_page.reload()
        assert resp.status == 200

    @sync
    async def test_emulate_navigator_online(self, isolated_page):
        def nav_online():
            return isolated_page.evaluate('() => window.navigator.onLine')

        assert await nav_online()
        await isolated_page.setOfflineMode(True)
        assert await nav_online() is False
        await isolated_page.setOfflineMode(False)
        assert await nav_online()


class TestExecutionContextQueryObjects:
    @sync
    async def test_queries_objects(self, isolated_page):
        await isolated_page.evaluate('() => window.set = new Set(["hello", "world"])')
        proto_handle = await isolated_page.evaluateHandle('() => Set.prototype')
        objs_handle = await isolated_page.queryObjects(proto_handle)
        # todo (Mattwmaster58): correct typing
        assert await isolated_page.evaluate('objects => objects.length', objs_handle) == 1
        assert await isolated_page.evaluate('objects => Array.from(objects[0].values())', objs_handle) == [
            'hello',
            'world',
        ]

    @sync
    async def test_queries_objects_non_blank_page(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate('() => window.set = new Set(["hello", "world"])')
        proto_handle = await isolated_page.evaluateHandle('() => Set.prototype')
        objs_handle = await isolated_page.queryObjects(proto_handle)
        # todo (Mattwmaster58): correct typing
        assert len(await isolated_page.evaluate('objects => objects.length', objs_handle)) == 1
        assert await isolated_page.evaluate('objects => Array.from(objects[0].values())', objs_handle) == [
            'hello',
            'world',
        ]

    @sync
    async def test_fails_on_disposed_handles(self, isolated_page):
        proto_handle = await isolated_page.evaluateHandle('() => HTMLBodyElement.prototype')
        await proto_handle.dispose()
        with pytest.raises(ElementHandleError) as excpt:
            await isolated_page.queryObjects(proto_handle)
        assert 'Prototype JSHandle is disposed' in str(excpt.value)

    @sync
    async def test_fail_on_primitive_vals_as_proto(self, isolated_page):
        proto_handle = await isolated_page.evaluateHandle('() => 42')
        with pytest.raises(ElementHandleError) as excpt:
            await isolated_page.queryObjects(proto_handle)
        assert 'Prototype JSHandle must not be referencing primitive value' in str(excpt.value)


class TestEventsConsole:
    @sync
    async def test_console_works(self, isolated_page):
        message: Optional[ConsoleMessage] = None

        def set_message(m):
            nonlocal message
            message = m

        isolated_page.once('console', set_message)
        await gather_with_timeout(
            isolated_page.evaluate('() => console.log("hello", 5, {foo: "bar"})'), waitEvent(isolated_page, 'console'),
        )
        assert message.text == 'hello 5 JSHandle@object'
        assert message.type == 'log'
        assert await message.args[0].jsonValue() == 'hello'
        assert await message.args[1].jsonValue() == 5
        assert await message.args[2].jsonValue() == {'foo': 'bar'}

    @sync
    async def test_different_console_apis(self, isolated_page):
        messages: List[ConsoleMessage] = []

        def append_msg(m):
            nonlocal messages
            messages.append(m)

        isolated_page.on('console', append_msg)
        await isolated_page.evaluate(
            """() => {
            // A pair of time/timeEnd generates only one Console API call.
            console.time('calling console.time');
            console.timeEnd('calling console.time');
            console.trace('calling console.trace');
            console.dir('calling console.dir');
            console.warn('calling console.warn');
            console.error('calling console.error');
            console.log(Promise.resolve('should not wait until resolved!'));
        }"""
        )
        assert [m.type for m in messages] == ['timeEnd', 'trace', 'dir', 'warning', 'error', 'log']
        assert 'calling console.time' in messages[0].text
        assert [m.text for m in messages[1:]] == [
            'calling console.trace',
            'calling console.dir',
            'calling console.warn',
            'calling console.error',
            'JSHandle@promise',
        ]

    @sync
    async def test_works_with_window_obj(self, isolated_page):
        message = None

        def set_message(m):
            nonlocal message
            message = m

        isolated_page.once('console', set_message)
        await gather_with_timeout(
            isolated_page.evaluate('() => console.error(window)'), waitEvent(isolated_page, 'console'),
        )
        assert message.text == 'JSHandle@object'

    @sync
    async def test_triggers_correct_log(self, isolated_page, firefox, server):
        await isolated_page.goto('about:blank')
        message, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'console'),
            isolated_page.evaluate('async url => fetch(url).catch(e => {})', server.empty_page),
        )
        assert 'Access-Control-Allow-Origin' in message.text
        if firefox:
            assert message.type == 'warn'
        else:
            assert message.type == 'error'

    @sync
    async def test_has_location_on_fetch_failure(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        message, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'console'),
            isolated_page.setContent('<script>fetch("http://wat");</script>', server.empty_page),
        )
        assert 'ERR_NAME_NOT_RESOLVED' in message.text
        assert message.type == 'error'
        assert message.location == {'url': 'http://wat/', 'lineNumber': None}

    @sync
    async def test_location_for_console_API_calls(self, isolated_page, server, firefox):
        await isolated_page.goto(server.empty_page)
        message, *_ = await gather_with_timeout(
            waitEvent(isolated_page, 'console'), isolated_page.goto(server / 'consolelog.html'),
        )
        assert message.text == 'yellow'
        assert message.type == 'log'
        assert message.location == {
            'url': server / 'consolelog.html',
            'lineNumber': 7,
            'columnNumber': 6 if firefox else 14,  # console.|log vs |console.log
        }

    # @see https://github.com/puppeteer/puppeteer/issues/3865
    @sync
    async def test_gracefully_accepts_messages_from_detached_iframes(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate(
            """async() => {
            // 1. Create a popup that Puppeteer is not connected to.
            const win = window.open(window.location.href, 'Title', 'toolbar=no,location=no,directories=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=780,height=200,top=0,left=0');
            await new Promise(x => win.onload = x);
            // 2. In this popup, create an iframe that console.logs a message.
            win.document.body.innerHTML = `<iframe src='/consolelog.html'></iframe>`;
            const frame = win.document.querySelector('iframe');
            await new Promise(x => frame.onload = x);
            // 3. After that, remove the iframe.
            frame.remove();
        }"""
        )
        popup_targ = [x for x in isolated_page.browserContext.targets() if x != isolated_page.target][0]
        # 4. Connect to the popup and make sure it doesn't throw.
        await popup_targ.page()


class TestEventsDOMContentLoaded:
    @sync
    async def test_domcontentloaded_fired(self, isolated_page):
        await isolated_page.goto('about:blank')
        await asyncio.wait_for(waitEvent(isolated_page, 'domcontentloaded'), timeout=5)


class TestMetrics:
    @staticmethod
    def check_metrics(metrics):
        metrics_to_check = {
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
        }
        for name, value in metrics.items():
            assert name in metrics_to_check, f'Unrecognized/duplicate metric: {name}'
            assert value >= 0
            metrics_to_check.remove(name)
        assert len(metrics_to_check) == 0

    @sync
    async def test_retrieval_of_metrics(self, isolated_page):
        await isolated_page.goto('about:blank')
        self.check_metrics(await isolated_page.metrics())

    @sync
    async def test_metrics_event_fired_on_console_timestamp(self, event_loop, isolated_page):
        await isolated_page.goto('about:blank')
        metrics = event_loop.create_future()

        def resolve_fut(res):
            nonlocal metrics
            metrics.set_result(res)

        isolated_page.once('metrics', resolve_fut)
        await isolated_page.evaluate('() => console.timeStamp("test42")')
        metrics = await asyncio.wait_for(metrics, 5)
        assert metrics['title'] == 'test42'


class TestWaitForRequest:
    @sync
    async def test_basic_wait_for_request_usage(
        self, isolated_page, server,
    ):
        await isolated_page.goto(server.empty_page)
        request, *_ = await gather_with_timeout(
            isolated_page.waitForRequest(server / 'digits/2.png'),
            isolated_page.evaluate(
                """() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }"""
            ),
        )
        assert request.url == server / 'digits/2.png'

    @sync
    async def test_works_with_predicate(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        request, *_ = await gather_with_timeout(
            isolated_page.waitForRequest(lambda r: r.url == server / 'digits/2.png'),
            isolated_page.evaluate(
                """() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }"""
            ),
        )
        assert request.url == server / 'digits/2.png'

    @sync
    async def test_respects_timeout(self, isolated_page):
        with pytest.raises(TimeoutError):
            await isolated_page.waitForRequest(lambda: False, timeout=1)

    @sync
    async def test_respects_default_timeout(self, isolated_page):
        isolated_page.setDefaultTimeout(1)
        with pytest.raises(TimeoutError):
            await isolated_page.waitForRequest(lambda: False)

    @sync
    async def test_works_with_no_timeout(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        request, *_ = await gather_with_timeout(
            isolated_page.waitForRequest(server / 'digits/2.png'),
            isolated_page.evaluate(
                """() => setTimeout(() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }, 50)"""
            ),
        )
        assert request.url == server / 'digits/2.png'


class TestWaitForResponse:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        response, *_ = await gather_with_timeout(
            isolated_page.waitForResponse(server / 'digits/2.png'),
            isolated_page.evaluate(
                """() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }"""
            ),
        )
        assert response.url == server / 'digits/2.png'

    @sync
    async def test_respects_timeout(self, isolated_page):
        with pytest.raises(TimeoutError):
            await isolated_page.waitForResponse(lambda: False, timeout=1),

    @sync
    async def test_respects_default_timeout(self, isolated_page):
        isolated_page.setDefaultTimeout(1)
        with pytest.raises(TimeoutError):
            await isolated_page.waitForResponse(lambda: False)

    @sync
    async def test_works_with_predicate(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        response, *_ = await gather_with_timeout(
            isolated_page.waitForResponse(lambda r: r.url == server / 'digits/2.png'),
            isolated_page.evaluate(
                """() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }"""
            ),
        )
        assert response.url == server / '/digits/2.png'

    @sync
    async def test_works_with_no_timeout(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        response, *_ = await gather_with_timeout(
            isolated_page.waitForResponse(server / 'digits/2.png', timeout=0),
            isolated_page.evaluate(
                """() => {
                fetch('/digits/1.png');
                fetch('/digits/2.png');
                fetch('/digits/3.png');
            }"""
            ),
        )
        assert response.url == server / 'digits/2.png'


class TestExposeFunction:
    @sync
    async def test_basic_usage(self, isolated_page):
        await isolated_page.exposeFunction('compute', lambda a, b: a * b)
        res = await isolated_page.evaluate('async() =>{  return await compute(9, 4); }')
        assert res == 36

    @sync
    async def test_raises_exception_in_page_context(self, isolated_page):
        def raise_me():
            raise Exception('WOOF WOOF')

        await isolated_page.exposeFunction('woof', raise_me)
        message, stack = await isolated_page.evaluate(
            """async() => {
            try {
                await woof();
            } catch (e) {
                return {message: e.message, stack: e.stack};
            }
        }
        """
        )
        assert message == 'WOOF WOOF'
        assert __file__ in stack

    @sync
    async def test_callable_within_evaluateOnNewDocument(self, isolated_page):
        called = False

        def set_called():
            nonlocal called
            called = True

        await isolated_page.exposeFunction('woof', set_called)
        await isolated_page.evaluateOnNewDocument('()=>woof()')
        await isolated_page.reload()
        assert called

    @sync
    async def test_survives_navigation(self, isolated_page, server):
        await isolated_page.exposeFunction('compute', lambda a, b: a * b)
        await isolated_page.goto(server.empty_page)
        res = await isolated_page.evaluate(
            """async function() {
            return await compute(9, 4);
        }"""
        )
        assert res == 36

    @sync
    async def test_awaits_returned_promise(self, isolated_page, event_loop):
        def compute(a, b):
            fut = event_loop.create_future()
            fut.set_result(a * b)
            return fut

        await isolated_page.exposeFunction('compute', compute)
        res = await isolated_page.evaluate(
            """async function() {
            return await compute(9, 4);
        }"""
        )
        assert res == 36

    @sync
    async def test_works_on_frames(self, isolated_page, server):
        await isolated_page.exposeFunction('compute', lambda a, b: a * b)
        await isolated_page.goto(server / 'frames/nested-frames.html')
        frame = isolated_page.frames[0]
        res = await frame.evaluate(
            """async function() {
            return await compute(9, 4);
        }"""
        )
        assert res == 36

    @sync
    async def test_works_on_frames_before_navigation(self, isolated_page, server):
        await isolated_page.goto(server / 'frames/nested-frames.html')
        await isolated_page.exposeFunction('compute', lambda a, b: a * b)
        frame = isolated_page.frames[0]
        res = await frame.evaluate(
            """async function() {
            return await compute(9, 4);
        }"""
        )
        assert res == 36

    @sync
    async def test_works_with_complex_obj(self, isolated_page):
        await isolated_page.exposeFunction('complexObject', lambda a, b: {'x': a['x'] * b['x']})
        res = await isolated_page.evaluate('async(a,b) => complexObject(a,b)', {'x': 9}, {'x': 4})
        assert res == {'x': 36}

    @sync
    async def test_works_with_async_exposed_func(self, isolated_page):
        async def my_async_func(a, b):
            return a * b

        await isolated_page.exposeFunction('compute', my_async_func)
        res = await isolated_page.evaluate(
            """async function() {
            return await compute(9, 4);
        }"""
        )
        assert res == 36


class TestEventsPageError:
    @sync
    async def test_pageerror_fired(self, isolated_page, server):
        error = None

        def set_error(e):
            nonlocal error
            error = e

        isolated_page.once('pageerror', set_error)
        await gather_with_timeout(isolated_page.goto(server / 'error.html'), waitEvent(isolated_page, 'pageerror'))
        assert 'Fancy' in str(error)


class TestSetUserAgent:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        assert 'Mozilla' in await isolated_page.evaluate("() => navigator.userAgent")
        await isolated_page.setUserAgent('foobar')
        request, *_ = await gather_with_timeout(
            server.app.waitForRequest(server.empty_page), isolated_page.goto(server.empty_page),
        )
        assert request.headers.get('user-agent') == 'foobar'

    @sync
    async def test_works_with_subframes(self, isolated_page, server):
        assert 'Mozilla' in await isolated_page.evaluate("() => navigator.userAgent")
        await isolated_page.setUserAgent('foobar')
        request, *_ = await gather_with_timeout(
            server.app.waitForRequest(server.empty_page), attachFrame(isolated_page, server.empty_page),
        )
        assert request.headers.get('user-agent') == 'foobar'

    @sync
    async def test_emulates_device_ua(self, isolated_page, server):
        await isolated_page.goto(server / 'mobile.html')
        assert 'iPhone' not in await isolated_page.evaluate("() => navigator.userAgent")
        await isolated_page.setUserAgent(devices['iPhone 6']['userAgent'])
        assert 'iPhone' in await isolated_page.evaluate("() => navigator.userAgent")


class TestSetContent:
    expected = '<html><head></head><body><div>hello</div></body></html>'

    @sync
    async def test_basic_usage(self, isolated_page):
        await isolated_page.setContent('<div>hello</div>')
        assert await isolated_page.content == self.expected

    @sync
    async def test_works_with_doctype(self, isolated_page):
        doctype = '<!DOCTYPE html>'
        await isolated_page.setContent(f'{doctype}<div>hello</div>')
        assert await isolated_page.content == f'{doctype}{self.expected}'

    @sync
    async def test_works_with_HTML4_doctype(self, isolated_page):
        doctype = '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">'
        await isolated_page.setContent(f'{doctype}<div>hello</div>')
        assert await isolated_page.content == f'{doctype}{self.expected}'

    @sync
    async def test_respects_timeout(self, isolated_page, server):
        img_path = server / 'img.png'
        # stall image response by 1s, causing the setContent to timeout
        server.app.add_request_precondition('/img.png', lambda: asyncio.sleep(1))
        with pytest.raises(TimeoutError):
            # note: timeout in ms
            await isolated_page.setContent(f'<img src="{img_path}"/>', timeout=1)

    @sync
    async def test_respects_default_timeout(self, isolated_page, server):
        img_path = server / 'img.png'
        # stall image response by 1s, causing the setContent to timeout
        server.app.add_request_precondition('/img.png', lambda: asyncio.sleep(1))
        # note: timeout in ms
        isolated_page.setDefaultNavigationTimeout(1)
        with pytest.raises(TimeoutError):
            await isolated_page.setContent(f'<img src="{img_path}"/>')

    @sync
    @pytest.mark.skip('need good way to determine if waiting for loading')
    async def test_awaits_loading_of_resources(self, event_loop, isolated_page, server):
        pass

    @sync
    async def test_works_with_badly_formed_input(self, isolated_page, server):
        await isolated_page.setContent('<div>Hello World</div>' + '\x7F')
        assert await isolated_page.Jeval('div', 'd => d.textContent') == 'Hello World'

    @sync
    async def test_works_with_accents(self, isolated_page, server):
        await isolated_page.setContent('<div>aberración</div>')
        assert await isolated_page.Jeval('div', 'd => d.textContent') == 'aberración'

    @sync
    async def test_works_with_emojis(self, isolated_page, server):
        await isolated_page.setContent('<div>🐥</div>')
        assert await isolated_page.Jeval('div', 'd => d.textContent') == '🐥'

    @sync
    async def test_works_with_newline(self, isolated_page, server):
        await isolated_page.setContent('<div>\n</div>')
        assert await isolated_page.Jeval('div', 'd => d.textContent') == '\n'


class TestSetBypassCSP:
    pass


class TestAddScriptTag:
    pass


class TestAddStyleTag:
    pass


class TestURL:
    pass


class TestSetJSEnabled:
    pass


class TestSetCacheEnabled:
    pass


class TestTitle:
    pass


class TestEventsClose:
    pass


class TestBrowser:
    pass


class TestBrowserContext:
    pass
