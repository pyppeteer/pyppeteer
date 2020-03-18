import pytest

from pyppeteer.helper import is_js_func

valid_js_functions = [
    # multiline func
    """
    function multiline(){
        console.log('hello');
    }
    """
    # functions w/o arguments
    'function (){console.log("hey")}',
    'function named() {console.log("hey")}',
    'async function () {console.log("hey")}',
    'async function named() {console.log("hey")}',
    '() => {console.log("hey")}',
    'async () => {console.log("hey")}',
    # functions with args, *args, and **kwargs
    'function (arg, *args, **kwargs){console.log("hey")}',
    'function named(arg, *args, **kwargs) {console.log("hey")}',
    'async function (arg, *args, **kwargs) {console.log("hey")}',
    'async function named(arg, *args, **kwargs) {console.log("hey")}',
    '(arg, *args, **kwargs) => {console.log("hey")}',
    'async (arg, *args, **kwargs) => {console.log("hey")}',
    # functions with args, *args, and **kwargs and no {} to define body
    '(arg, *args, **kwargs) => console.log("hey")',
    'async (arg, *args, **kwargs) => console.log("hey")',
]
invalid_js_functions = [
    # self executing function statements
    """
    (function (){
        console.log("hey");
    })()
    """,
    '(()=>console.log("hey"))()',
    '((arg, *args, **kwargs)=>console.log("hey"))(1,2,3)',
    'func=()=>console.log("hey");func()',
    'func=(arg, *args, **kwargs)=>console.log("hey");func()',
]

input_expected = [(x, True) for x in valid_js_functions] + [(x, False) for x in invalid_js_functions]


@pytest.mark.parametrize('js_str,expected', input_expected)
def test_is_js_func(js_str, expected):
    assert is_js_func(js_str) == expected
