#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import ElementHandleError, NetworkError

from .base import BaseTestCase


class TestQueryObject(BaseTestCase):
    @sync
    async def test_query_objects(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate(
            '() => window.set = new Set(["hello", "world"])'
        )
        prototypeHandle = await self.page.evaluateHandle('() => Set.prototype')
        objectsHandle = await self.page.queryObjects(prototypeHandle)
        count = await self.page.evaluate(
            'objects => objects.length',
            objectsHandle,
        )
        self.assertEqual(count, 1)
        values = await self.page.evaluate(
            'objects => Array.from(objects[0].values())',
            objectsHandle,
        )
        self.assertEqual(values, ['hello', 'world'])

    @sync
    async def test_query_objects_disposed(self):
        await self.page.goto(self.url + 'empty')
        prototypeHandle = await self.page.evaluateHandle(
            '() => HTMLBodyElement.prototype'
        )
        await prototypeHandle.dispose()
        with self.assertRaises(ElementHandleError):
            await self.page.queryObjects(prototypeHandle)

    @sync
    async def test_query_objects_primitive_value_error(self):
        await self.page.goto(self.url + 'empty')
        prototypeHandle = await self.page.evaluateHandle('() => 42')
        with self.assertRaises(ElementHandleError):
            await self.page.queryObjects(prototypeHandle)


class TestJSHandle(BaseTestCase):
    @sync
    async def test_get_property(self):
        handle1 = await self.page.evaluateHandle(
            '() => ({one: 1, two: 2, three: 3})'
        )
        handle2 = await handle1.getProperty('two')
        self.assertEqual(await handle2.jsonValue(), 2)

    @sync
    async def test_json_value(self):
        handle1 = await self.page.evaluateHandle('() => ({foo: "bar"})')
        json = await handle1.jsonValue()
        self.assertEqual(json, {'foo': 'bar'})

    @sync
    async def test_json_date_fail(self):
        handle = await self.page.evaluateHandle(
            '() => new Date("2017-09-26T00:00:00.000Z")'
        )
        json = await handle.jsonValue()
        self.assertEqual(json, {})

    @sync
    async def test_json_circular_object_error(self):
        windowHandle = await self.page.evaluateHandle('window')
        with self.assertRaises(NetworkError) as cm:
            await windowHandle.jsonValue()
        self.assertIn('Object reference chain is too long',
                      cm.exception.args[0])

    @sync
    async def test_get_properties(self):
        handle1 = await self.page.evaluateHandle('() => ({foo: "bar"})')
        properties = await handle1.getProperties()
        foo = properties.get('foo')
        self.assertTrue(foo)
        self.assertEqual(await foo.jsonValue(), 'bar')

    @sync
    async def test_return_non_own_properties(self):
        aHandle = await self.page.evaluateHandle('''() => {
            class A {
                constructor() {
                    this.a = '1';
                }
            }
            class B extends A {
                constructor() {
                    super();
                    this.b = '2';
                }
            }
            return new B();
        }''')
        properties = await aHandle.getProperties()
        self.assertEqual(await properties.get('a').jsonValue(), '1')
        self.assertEqual(await properties.get('b').jsonValue(), '2')

    @sync
    async def test_as_element(self):
        aHandle = await self.page.evaluateHandle('() => document.body')
        element = aHandle.asElement()
        self.assertTrue(element)

    @sync
    async def test_as_element_non_element(self):
        aHandle = await self.page.evaluateHandle('() => 2')
        element = aHandle.asElement()
        self.assertIsNone(element)

    @sync
    async def test_as_element_text_node(self):
        await self.page.setContent('<div>ee!</div>')
        aHandle = await self.page.evaluateHandle(
            '() => document.querySelector("div").firstChild')
        element = aHandle.asElement()
        self.assertTrue(element)
        self.assertTrue(await self.page.evaluate(
            '(e) => e.nodeType === HTMLElement.TEXT_NODE',
            element,
        ))

    @sync
    async def test_to_string_number(self):
        handle = await self.page.evaluateHandle('() => 2')
        self.assertEqual(handle.toString(), 'JSHandle:2')

    @sync
    async def test_to_string_str(self):
        handle = await self.page.evaluateHandle('() => "a"')
        self.assertEqual(handle.toString(), 'JSHandle:a')

    @sync
    async def test_to_string_complicated_object(self):
        handle = await self.page.evaluateHandle('() => window')
        self.assertEqual(handle.toString(), 'JSHandle@object')
