import pytest
from syncer import sync

from pyppeteer.errors import NetworkError
from tests.conftest import CHROME


@sync
async def test_handle(isolated_page, server):
    """test getting handle"""
    p = isolated_page
    assert await p.evaluateHandle('window')


@sync
@pytest.mark.skip('NotImplemented - evaluate functions do not support obj references')
async def test_handle_with_arg(isolated_page, server):
    """test getting handle"""
    p = isolated_page
    navigatorHandle = await p.evaluateHandle("navigator")
    # this should be able to take local reference
    text = await p.evaluate('e => e.userAgent', navigatorHandle)
    assert 'Mozilla' in text


@sync
async def test_handle_primitive_types(isolated_page, server):
    """test getting handle"""
    p = isolated_page
    handle = await p.evaluateHandle('5')
    assert p.evaluate('e => Object.is(e, 5)', handle)


@sync
async def test_warn_nested_handles(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle('document.body')
    await p.evaluateHandle(
        "opts => opts.elem.querySelector('p')",
        handle,  # todo translate {elem: handle}
    )


@sync
async def test_handle_unserializable(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle('Infinity')
    assert await p.evaluate('e => Object.is(e, Infinity)', handle) is True


@sync
async def test_js_wrappers(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle("""
        () => {
            window.Foo = 123;
            return window;    
        }
    """.strip())
    assert await p.evaluate('e => e.Foo', handle) == 123


@sync
async def test_with_primitives(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle("""
        () => {
            window.Foo = 123;
            return window;    
        }
    """.strip())
    assert await p.evaluate('e => e.Foo', handle) == 123


@sync
async def test_getProperty(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle("""
        () => ({
            one: 1,
            two: 2,
            three: 3
        })
    """.strip())
    handle2 = await handle.getProperty('two')
    assert await handle2.jsonValue() == 2


@sync
async def test_jsonValue(isolated_page, server):
    # should work with json values
    p = isolated_page
    handle = await p.evaluateHandle('() => ({foo: "bar"})')
    assert await handle.jsonValue() == {'foo': 'bar'}

    # should not work with dates
    handle_date = await p.evaluateHandle(
        "new Date('2017-09-26T00:00:00.000Z')"
    )
    assert await handle_date.jsonValue() == {}

    # should throw for circular objects like windows
    handle_window = await p.evaluateHandle('window')
    with pytest.raises(NetworkError) as e:
        await handle_window.jsonValue()
    if CHROME:
        assert e.match('Object reference chain is too long')
    else:
        assert e.match('Object is not serial')


@sync
async def test_getProperties(isolated_page, server):
    p = isolated_page
    handle = await p.evaluateHandle('({foo: "bar"})')
    properties = await handle.getProperties()
    foo = properties.get('foo')
    assert foo
    assert await foo.jsonValue() == 'bar'

    # should return even non-own properties
    handle = await p.evaluateHandle(
        """
        () => {
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

            return new B()
        }
        """)
    properties = await handle.getProperties()
    assert await properties.get('a').jsonValue() == '1'
    assert await properties.get('b').jsonValue() == '2'


@sync
async def test_asElement(isolated_page, server):
    p = isolated_page
    # should work
    handle = await p.evaluateHandle("document.body")
    assert handle.asElement()

    # should return None for non-elements
    handle = await p.evaluateHandle("2")
    element = handle.asElement()
    assert element is None

    # should return ElementHandle for TextNodes
    await p.setContent('<div>ee!</div>')
    handle = await p.evaluateHandle(
        "document.querySelector('div').firstChild"
    )
    element = handle.asElement()
    assert element
    # python doesn't support object passover
    # assert await p.evaluate(
    #     'e => e.nodeType === HTMLElement.TEXT_NODE, arg',
    #     element
    # )

    # should work with nulified None
    await p.setContent('<section>test</section>')
    await p.evaluate('delete Node')
    handle = await p.evaluateHandle(
        'document.querySelector("section")'
    )
    assert handle.asElement()


@sync
async def test_toString(isolated_page, server):
    p = isolated_page
    input_to_expected = {
        # should work for primitives
        '2': 'JSHandle:2',
        '"a"': 'JSHandle:a',
        # should work for complicated objects
        'window': 'JSHandle@object',
        # should work with different subtypes
        '(function(){})': 'JSHandle@function',
        '12': 'JSHandle:12',
        'true': 'JSHandle:True',
        'undefined': 'JSHandle:None',
        '"foo"': 'JSHandle:foo',
        'Symbol()': 'JSHandle@symbol',
        'new Set()': 'JSHandle@set',
        'new Map()': 'JSHandle@map',
        '[]': 'JSHandle@array',
        'null': 'JSHandle:None',
        '/foo/': 'JSHandle@regexp',
        'document.body': 'JSHandle@node',
        'new Date()': 'JSHandle@date',
        'new WeakMap()': 'JSHandle@weakmap',
        'new Error()': 'JSHandle@error',
        'new Int32Array()': 'JSHandle@typedarray',
        'new Proxy({}, {})': 'JSHandle@proxy',

    }
    for value, expected in input_to_expected.items():
        handle = await p.evaluateHandle(value)
        assert handle.toString() == expected

