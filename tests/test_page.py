#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import math
import unittest

from syncer import sync

from pyppeteer.errors import ElementHandleError

from base import BaseTestCase
from frame_utils import attachFrame


class TestEvaluate(BaseTestCase):
    @sync
    async def test_evaluate(self):
        result = await self.page.evaluate('() => 7 * 3')
        self.assertEqual(result, 21)

    @sync
    async def test_await_promise(self):
        result = await self.page.evaluate('() => Promise.resolve(8 * 7)')
        self.assertEqual(result, 56)

    @sync
    async def test_after_framenavigation(self):
        frameEvaluation = asyncio.get_event_loop().create_future()

        async def evaluate_frame(frame):
            frameEvaluation.set_result(await frame.evaluate('() => 6 * 7'))

        self.page.on(
            'framenavigated',
            lambda frame: asyncio.ensure_future(evaluate_frame(frame)),
        )
        await self.page.goto(self.url + 'empty')
        await frameEvaluation
        self.assertEqual(frameEvaluation.result(), 42)

    @unittest.skip('Cannot pass this test')
    @sync
    async def test_inside_expose_function(self):
        async def callController(a, b):
            result = await self.page.evaluate('(a, b) => a + b', a, b)
            return result

        await self.page.exposeFunction(
            'callController',
            lambda *args: asyncio.ensure_future(callController(*args))
        )
        result = await self.page.evaluate(
            'async function() { return await callController(9, 3); }'
        )
        self.assertEqual(result, 27)

    @sync
    async def test_paromise_reject(self):
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('() => not.existing.object.property')
        self.assertIn('not is not defined', cm.exception.args[0])

    @sync
    async def test_return_complex_object(self):
        obj = {'foo': 'bar!'}
        result = await self.page.evaluate('(a) => a', obj)
        self.assertIsNot(result, obj)
        self.assertEqual(result, obj)

    @sync
    async def test_return_nan(self):
        result = await self.page.evaluate('() => NaN')
        self.assertIsNone(result)

    @sync
    async def test_return_minus_zero(self):
        result = await self.page.evaluate('() => -0')
        self.assertEqual(result, -0)

    @sync
    async def test_return_infinity(self):
        result = await self.page.evaluate('() => Infinity')
        self.assertEqual(result, math.inf)

    @sync
    async def test_return_infinity_minus(self):
        result = await self.page.evaluate('() => -Infinity')
        self.assertEqual(result, -math.inf)

    @sync
    async def test_accept_none(self):
        result = await self.page.evaluate(
            '(a, b) => Object.is(a, null) && Object.is(b, "foo")',
            None, 'foo',
        )
        self.assertTrue(result)

    @unittest.skip('Cannot pass this  test')
    @sync
    async def test_serialize_null_field(self):
        result = await self.page.evaluate('() => {a: undefined}')
        self.assertEqual(result, {})

    @unittest.skip('Cannot pass this  test')
    @sync
    async def test_fail_window_object(self):
        result = await self.page.evaluate('() => window')
        self.assertIsNone(result)

    @sync
    async def test_accept_string(self):
        result = await self.page.evaluate('1 + 2')
        self.assertEqual(result, 3)

    @sync
    async def test_accept_string_with_semicolon(self):
        result = await self.page.evaluate('1 + 5;')
        self.assertEqual(result, 6)

    @sync
    async def test_accept_string_with_comments(self):
        result = await self.page.evaluate('2 + 5;\n// do some math!')
        self.assertEqual(result, 7)

    @sync
    async def test_element_handle_as_argument(self):
        await self.page.setContent('<section>42</section>')
        element = await self.page.J('section')
        text = await self.page.evaluate('(e) => e.textContent', element)
        self.assertEqual(text, '42')

    @sync
    async def test_element_handle_disposed(self):
        await self.page.setContent('<section>39</section>')
        element = await self.page.J('section')
        self.assertTrue(element)
        await element.dispose()
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('(e) => e.textContent', element)
        self.assertIn('JSHandle is disposed', cm.exception.args[0])

    @sync
    async def test_element_handle_from_other_frame(self):
        await attachFrame(self.page, 'frame1', self.url + 'empty')
        body = await self.page.frames[1].J('body')
        with self.assertRaises(ElementHandleError) as cm:
            await self.page.evaluate('body => body.innerHTML', body)
        self.assertIn(
            'JSHandles can be evaluated only in the context they were created',
            cm.exception.args[0],
        )

    @sync
    async def test_object_handle_as_argument(self):
        navigator = await self.page.evaluateHandle('() => navigator')
        self.assertTrue(navigator)
        text = await self.page.evaluate('(e) => e.userAgent', navigator)
        self.assertIn('Mozilla', text)

    @sync
    async def test_object_handle_to_primitive_value(self):
        aHandle = await self.page.evaluateHandle('() => 5')
        isFive = await self.page.evaluate('(e) => Object.is(e, 5)', aHandle)
        self.assertTrue(isFive)
