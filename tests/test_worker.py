#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

from syncer import sync


class TestWorker:
    @sync
    async def test_worker(self, isolated_page, server):
        await isolated_page.goto(server / 'assets/worker/worker.html')
        await isolated_page.waitForFunction('() => !!worker')
        worker = isolated_page.workers[0]
        assert 'worker.js' in worker.url
        executionContext = await worker.executionContext
        assert await executionContext.evaluate('self.workerFunction()') == 'worker function result'

    @sync
    async def test_create_destroy_events(self, isolated_page, event_loop):
        workerCreatedPromise = event_loop.create_future()
        isolated_page.once('workercreated', lambda w: workerCreatedPromise.set_result(w))
        workerObj = await isolated_page.evaluateHandle('() => new Worker("data:text/javascript,1")')
        worker = await workerCreatedPromise
        workerDestroyedPromise = asyncio.get_event_loop().create_future()
        isolated_page.once('workerdestroyed', lambda w: workerDestroyedPromise.set_result(w))
        await isolated_page.evaluate('workerObj => workerObj.terminate()', workerObj)
        assert await workerDestroyedPromise == worker

    @sync
    async def test_report_console_logs(self, isolated_page):
        logPromise = asyncio.get_event_loop().create_future()
        isolated_page.once('console', lambda m: logPromise.set_result(m))
        await isolated_page.evaluate('() => new Worker("data:text/javascript,console.log(1)")')
        log = await logPromise
        assert log.text == '1'
        assert log.location == {
            'url': 'data:text/javascript,console.log(1)',
            'lineNumber': 0,
            'columnNumber': 8,
        }

    @sync
    async def test_jshandle_for_console_log(self, isolated_page):
        logPromise = asyncio.get_event_loop().create_future()
        isolated_page.on('console', lambda m: logPromise.set_result(m))
        await isolated_page.evaluate('() => new Worker("data:text/javascript,console.log(1,2,3,this)")')
        log = await logPromise
        assert log.text == '1 2 3 JSHandle@object'
        assert len(log.args) == 4
        assert await (await log.args[3].getProperty('origin')).jsonValue() == 'null'

    @sync
    async def test_execution_context(self, isolated_page):
        workerCreatedPromise = asyncio.get_event_loop().create_future()
        isolated_page.once('workercreated', lambda w: workerCreatedPromise.set_result(w))
        await isolated_page.evaluate('() => new Worker("data:text/javascript,console.log(1)")')
        ctx = await (await workerCreatedPromise).executionContext
        assert await ctx.evaluate('1+1') == 2

    @sync
    async def test_report_error(self, isolated_page):
        errorPromise = asyncio.get_event_loop().create_future()
        isolated_page.on('pageerror', lambda x: errorPromise.set_result(x))
        await isolated_page.evaluate(
            '() => new Worker(`data:text/javascript, throw new Error("this is my error");`)'
        )
        errorLog = await errorPromise
        assert 'this is my error' in errorLog.args[0]
