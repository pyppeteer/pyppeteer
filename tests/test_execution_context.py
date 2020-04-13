#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from pyppeteer.errors import ElementHandleError, NetworkError


import pytest


class TestQueryObject:
    @sync
    async def test_query_objects(self):
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('() => window.set = new Set(["hello", "world"])')
        prototypeHandle = await self.page.evaluateHandle('() => Set.prototype')
        objectsHandle = await self.page.queryObjects(prototypeHandle)
        count = await self.page.evaluate('objects => objects.length', objectsHandle,)
        assert count == 1
        values = await self.page.evaluate('objects => Array.from(objects[0].values())', objectsHandle,)
        assert values == ['hello', 'world']

    @sync
    async def test_query_objects_disposed(self):
        await self.page.goto(self.url + 'empty')
        prototypeHandle = await self.page.evaluateHandle('() => HTMLBodyElement.prototype')
        await prototypeHandle.dispose()
        with pytest.raises(ElementHandleError):
            await self.page.queryObjects(prototypeHandle)

    @sync
    async def test_query_objects_primitive_value_error(self):
        await self.page.goto(self.url + 'empty')
        prototypeHandle = await self.page.evaluateHandle('() => 42')
        with pytest.raises(ElementHandleError):
            await self.page.queryObjects(prototypeHandle)


class TestJSHandle:
    @sync
    async def test_get_property(self):
        handle1 = await self.page.evaluateHandle('() => ({one: 1, two: 2, three: 3})')
        handle2 = await handle1.getProperty('two')
        assert await handle2.jsonValue() == 2

    @sync
    async def test_json_value(self):
        handle1 = await self.page.evaluateHandle('() => ({foo: "bar"})')
        json = await handle1.jsonValue()
        assert json == {'foo': 'bar'}

    @sync
    async def test_json_date_fail(self):
        handle = await self.page.evaluateHandle('() => new Date("2017-09-26T00:00:00.000Z")')
        json = await handle.jsonValue()
        assert json == {}

    @sync
    async def test_json_circular_object_error(self):
        windowHandle = await self.page.evaluateHandle('window')
        with pytest.raises(NetworkError, match='Object reference chain is too long') as cm:
            await windowHandle.jsonValue()

    @sync
    async def test_get_properties(self):
        handle1 = await self.page.evaluateHandle('{foo: "bar"}')
        properties = await handle1.getProperties()
        foo = properties.get('foo')
        assert foo
        assert await foo.jsonValue() == 'bar'

    @sync
    async def test_return_non_own_properties(self):
        aHandle = await self.page.evaluateHandle(
            '''() => {
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
        }'''
        )
        properties = await aHandle.getProperties()
        assert await properties.get('a').jsonValue() == '1'
        assert await properties.get('b').jsonValue() == '2'

    @sync
    async def test_as_element(self):
        aHandle = await self.page.evaluateHandle('() => document.body')
        element = aHandle.asElement()
        assert element

    @sync
    async def test_as_element_non_element(self):
        aHandle = await self.page.evaluateHandle('() => 2')
        element = aHandle.asElement()
        assert element is None

    @sync
    async def test_as_element_text_node(self):
        await self.page.setContent('<div>ee!</div>')
        aHandle = await self.page.evaluateHandle('() => document.querySelector("div").firstChild')
        element = aHandle.asElement()
        assert element
        assert await self.page.evaluate('(e) => e.nodeType === HTMLElement.TEXT_NODE', element,)

    @sync
    async def test_to_string_number(self):
        handle = await self.page.evaluateHandle('() => 2')
        assert handle.toString() == 'JSHandle:2'

    @sync
    async def test_to_string_str(self):
        handle = await self.page.evaluateHandle('() => "a"')
        assert handle.toString() == 'JSHandle:a'

    @sync
    async def test_to_string_complicated_object(self):
        handle = await self.page.evaluateHandle('() => window')
        assert handle.toString() == 'JSHandle@object'
