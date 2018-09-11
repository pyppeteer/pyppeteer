#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

from syncer import sync

from .base import BaseTestCase


class TestWorker(BaseTestCase):
    @sync
    async def test_worker(self):
        await self.page.goto(self.url + 'static/worker/worker.html')
        await self.page.waitForFunction('() => !!worker')
        worker = self.page.workers[0]
        self.assertIn('worker.js', worker.url)
        executionContext = await worker.executionContext()
        self.assertEqual(
            await executionContext.evaluate('self.workerFunction()'),
            'worker function result',
        )

    @sync
    async def test_create_destroy_events(self):
        workerCreatedPromise = asyncio.get_event_loop().create_future()
        self.page.once('workercreated',
                       lambda w: workerCreatedPromise.set_result(w))
        workerObj = await self.page.evaluateHandle(
            '() => new Worker("data:text/javascript,1")')
        worker = await workerCreatedPromise
        workerDestroyedPromise = asyncio.get_event_loop().create_future()
        self.page.once('workerdestroyed',
                       lambda w: workerDestroyedPromise.set_result(w))
        await self.page.evaluate(
            'workerObj => workerObj.terminate()', workerObj)
        self.assertEqual(await workerDestroyedPromise, worker)

    @sync
    async def test_report_console_logs(self):
        logPromise = asyncio.get_event_loop().create_future()
        self.page.once('console', lambda m: logPromise.set_result(m))
        await self.page.evaluate(
            '() => new Worker("data:text/javascript,console.log(1)")'
        )
        log = await logPromise
        self.assertEqual(log.text, '1')

    @sync
    async def test_jshandle_for_console_log(self):
        logPromise = asyncio.get_event_loop().create_future()
        self.page.on('console', lambda m: logPromise.set_result(m))
        await self.page.evaluate(
            '() => new Worker("data:text/javascript,console.log(1,2,3,this)")')
        log = await logPromise
        self.assertEqual(log.text, '1 2 3 JSHandle@object')
        self.assertEqual(len(log.args), 4)
        self.assertEqual(
            await (await log.args[3].getProperty('origin')).jsonValue(),
            'null',
        )

    @sync
    async def test_execution_context(self):
        workerCreatedPromise = asyncio.get_event_loop().create_future()
        self.page.once('workercreated',
                       lambda w: workerCreatedPromise.set_result(w))
        await self.page.evaluate(
            '() => new Worker("data:text/javascript,console.log(1)")')
        worker = await workerCreatedPromise
        self.assertEqual(
            await (await worker.executionContext()).evaluate('1+1'), 2)
        self.assertEqual(await worker.evaluate('1+2'), 3)

    @sync
    async def test_report_error(self):
        errorPromise = asyncio.get_event_loop().create_future()
        self.page.on('pageerror', lambda x: errorPromise.set_result(x))
        await self.page.evaluate('() => new Worker(`data:text/javascript, throw new Error("this is my error");`)')  # noqa: E501
        errorLog = await errorPromise
        self.assertIn('this is my error', errorLog.args[0])
