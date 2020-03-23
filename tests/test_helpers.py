import pytest

from pyppeteer.helpers import is_js_func

valid_js_functions = [
    # functions w/o opening/closing parens and w/o opening/closing body
    'singlearg=>{console.log("hey")}',
    'async singlearg=>{console.log("hey")}',
    'singlearg=>console.log("hey")',
    'async singlearg=>console.log("hey")',
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
    'function named(arg, ars) {console.log("hey")}',
    'async function (arg, ars) {console.log("hey")}',
    'async function named(arg, ars) {console.log("hey")}',
    '(arg, ars) => {console.log("hey")}',
    'async (arg, ars) => {console.log("hey")}',
    # functions with multiple args with no {} to define body
    '(arg, ars) => console.log("hey")',
    'async (arg, args) => console.log("hey")',
    # functions using spread operator
    '(...spread)=>{console.log("hey")}'
    'async (...spread)=>{console.log("hey")}'
    'async function (...spread){console.log("hey")}'
    'async function named(...spread){console.log("hey")}'
    '(arg1, ...spread)=>{console.log("hey")}'
    'async (arg1, ...spread)=>{console.log("hey")}'
    'async function (arg1, ...spread){console.log("hey")}'
    'async function named(arg1, ...spread){console.log("hey")}'
]
invalid_js_functions = [
    # Immediately-Invoked Function Expressions
    """
    (function (){
        console.log("hey");
    })()
    """,
    '(()=>console.log("hey"))()',
    '((arg, *args, **kwargs)=>console.log("hey"))(1,2,3)',
    # Function assignments
    'func=()=>console.log("hey");func()',
    'func=(arg, *args, **kwargs)=>console.log("hey");func()',
    # almost valid functions
    'arg1,arg2=>{console.log("hey")}',
    '*arg=>{console.log("hey")}',
    '...args=>{console.log("hey")}'
]

input_expected = [(x, True) for x in valid_js_functions] + [(x, False) for x in invalid_js_functions]


@pytest.mark.parametrize('js_str,expected', input_expected)
def test_is_js_func(js_str, expected):
    assert is_js_func(js_str) == expected
