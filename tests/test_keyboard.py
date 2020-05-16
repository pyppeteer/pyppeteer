import textwrap

import pytest
from syncer import sync

from pyppeteer.errors import PyppeteerError
from tests.utils import attachFrame


def retrieve_textarea_value(page_or_frame):
    return page_or_frame.evaluate('document.querySelector("textarea").value')


def exec_get_res(page):
    return page.evaluate('getResult()')


@sync
async def test_typing_in_text_area(isolated_page):
    await isolated_page.evaluate(
        '''() => {
        const textarea = document.createElement('textarea')
        document.body.appendChild(textarea)
        textarea.focus()
    }'''
    )
    text = 'Hello world. I am the text that was typed!'
    await isolated_page.keyboard.type(text)
    assert await retrieve_textarea_value(isolated_page) == text


@sync
async def test_moves_with_arrow_keys(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    initial_text = 'Hello World!'
    inserted_text = 'Hello inserted World!'
    await isolated_page.type('textarea', initial_text)
    assert await retrieve_textarea_value(isolated_page) == initial_text

    for _ in 'World!':
        await isolated_page.keyboard.press('ArrowLeft')

    await isolated_page.keyboard.type('inserted ')
    assert await retrieve_textarea_value(isolated_page) == inserted_text

    await isolated_page.keyboard.down('Shift')
    for _ in 'inserted ':
        await isolated_page.keyboard.press('ArrowLeft')

    await isolated_page.keyboard.up('Shift')
    await isolated_page.keyboard.press('Backspace')

    assert await retrieve_textarea_value(isolated_page) == initial_text


@sync
async def test_sends_a_char_with_elementhandle_press(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    textarea = await isolated_page.J('textarea')
    await textarea.press('a')
    assert await retrieve_textarea_value(isolated_page) == 'a'

    await isolated_page.evaluate('window.addEventListener("keydown", e => e.preventDefault(), true)')

    await textarea.press('b')
    assert await retrieve_textarea_value(isolated_page) == 'a'


@sync
async def test_elementhandle_press_supports_text_option(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    textarea = await isolated_page.J('textarea')
    await textarea.press('a', text='ё')
    assert await retrieve_textarea_value(isolated_page) == 'ё'


@sync
async def test_sends_char_with_sendcharacter(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    await isolated_page.focus('textarea')
    await isolated_page.keyboard.sendCharacter('嗨')
    assert await retrieve_textarea_value(isolated_page) == '嗨'
    await isolated_page.evaluate('window.addEventListener("keydown", e => e.preventDefault(), true)')
    await isolated_page.keyboard.sendCharacter('a')
    assert await retrieve_textarea_value(isolated_page) == '嗨a'


@sync
async def test_reports_shift_key(isolated_page, server):
    await isolated_page.goto(server / 'input/keyboard.html')
    keyboard = isolated_page.keyboard

    code_for_key = {'Shift': 16, 'Control': 17, 'Alt': 18}

    for modkey, code in code_for_key.items():
        await keyboard.down(modkey)
        assert await exec_get_res(isolated_page) == f'Keydown: {modkey} {modkey}Left {code} [{modkey}]'
        await keyboard.down('!')

        expected_res = f'Keydown: ! Digit1 49 [{modkey}]'
        # Shift+! generates a keypress
        if modkey == 'Shift':
            expected_res += f'\nKeypress: ! Digit1 33 33 [{modkey}]'
        assert await exec_get_res(isolated_page) == expected_res

        await keyboard.up('!')
        assert await exec_get_res(isolated_page) == f'Keyup: ! Digit1 49 [{modkey}]'
        await keyboard.up(modkey)
        assert await exec_get_res(isolated_page) == f'Keyup: {modkey} {modkey}Left {code} []'


@sync
async def test_reports_multiples_modifiers(isolated_page, server):
    await isolated_page.goto(server / 'input/keyboard.html')
    keyboard = isolated_page.keyboard

    await keyboard.down('Control')
    assert await exec_get_res(isolated_page) == 'Keydown: Control ControlLeft 17 [Control]'
    await keyboard.down('Alt')
    assert await exec_get_res(isolated_page) == 'Keydown: Alt AltLeft 18 [Alt Control]'
    await keyboard.down(';')
    assert await exec_get_res(isolated_page) == 'Keydown: ; Semicolon 186 [Alt Control]'
    await keyboard.up(';')
    assert await exec_get_res(isolated_page) == 'Keyup: ; Semicolon 186 [Alt Control]'
    await keyboard.up('Control')
    assert await exec_get_res(isolated_page) == 'Keyup: Control ControlLeft 17 [Alt]'
    await keyboard.up('Alt')
    assert await exec_get_res(isolated_page) == 'Keyup: Alt AltLeft 18 []'


@sync
async def test_sends_proper_codes_while_typing(isolated_page, server):
    await isolated_page.goto(server / 'input/keyboard.html')
    await isolated_page.keyboard.type('!')
    assert await exec_get_res(isolated_page) == textwrap.dedent(
        '''\
        Keydown: ! Digit1 49 []
        Keypress: ! Digit1 33 33 []
        Keyup: ! Digit1 49 []'''
    )
    await isolated_page.keyboard.type('^')
    assert await exec_get_res(isolated_page) == textwrap.dedent(
        '''\
        Keydown: ^ Digit6 54 []
        Keypress: ^ Digit6 94 94 []
        Keyup: ^ Digit6 54 []'''
    )


@sync
async def test_sends_proper_codes_while_typing_with_shift(isolated_page, server):
    await isolated_page.goto(server / 'input/keyboard.html')
    await isolated_page.keyboard.down('Shift')
    await isolated_page.keyboard.type('~')
    assert await exec_get_res(isolated_page) == textwrap.dedent(
        '''\
            Keydown: Shift ShiftLeft 16 [Shift]
            Keydown: ~ Backquote 192 [Shift]
            Keypress: ~ Backquote 126 126 [Shift]
            Keyup: ~ Backquote 192 [Shift]'''
    )
    await isolated_page.keyboard.up('Shift')


@sync
async def test_doesnt_type_canceled_events(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    await isolated_page.focus('textarea')
    await isolated_page.evaluate(
        '''() => {
        window.addEventListener('keydown', event => {
            event.stopPropagation()
            event.stopImmediatePropagation()
            if (event.key === 'l' || event.key === 'o') { event.preventDefault() }
        }, false)
    }'''
    )
    await isolated_page.keyboard.type('Hello World!')
    assert await retrieve_textarea_value(isolated_page) == 'He Wrd!'


@sync
async def test_specifies_repeat_property(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    await isolated_page.focus('textarea')
    await isolated_page.evaluate(
        'document.querySelector("textarea").addEventListener("keydown", e => window.lastEvent = e, true)'
    )
    await isolated_page.keyboard.down('a')
    assert await isolated_page.evaluate('window.lastEvent.repeat') is False
    await isolated_page.keyboard.press('a')
    assert await isolated_page.evaluate('window.lastEvent.repeat')

    await isolated_page.keyboard.down('b')
    assert await isolated_page.evaluate('window.lastEvent.repeat') is False
    await isolated_page.keyboard.down('b')
    assert await isolated_page.evaluate('window.lastEvent.repeat')

    await isolated_page.keyboard.up('a')
    await isolated_page.keyboard.down('a')
    assert await isolated_page.evaluate('window.lastEvent.repeat') is False


@sync
async def test_types_all_kinds_of_chars(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    await isolated_page.evaluate(
        '''() => {
        window.addEventListener('keydown', event => window.keyLocation = event.location, true)
    }'''
    )
    textarea = await isolated_page.J('textarea')

    await textarea.press('Digit5')
    assert await isolated_page.evaluate('keyLocation') == 0

    await textarea.press('ControlLeft')
    assert await isolated_page.evaluate('keyLocation') == 1

    await textarea.press('ControlRight')
    assert await isolated_page.evaluate('keyLocation') == 2

    await textarea.press('NumpadSubtract')
    assert await isolated_page.evaluate('keyLocation') == 3


@sync
async def test_raises_on_unknown_keys(isolated_page, server):
    for key in ['NotARealKey', 'ё', '😊']:
        with pytest.raises(PyppeteerError, match=f'Unknown key: "{key}"') as excpt:
            await isolated_page.keyboard.press(key)


@sync
async def test_types_emoji(isolated_page, server):
    await isolated_page.goto(server / 'input/textarea.html')
    text = '👹 Tokyo street Japan 🇯🇵'
    await isolated_page.type('textarea', text)
    assert await retrieve_textarea_value(isolated_page) == text


@sync
async def test_types_emoji_in_iframe(isolated_page, server):
    await isolated_page.goto(server.empty_page)
    await attachFrame(isolated_page, server / 'input/textarea.html')
    frame = isolated_page.frames[1]
    text = '👹 Tokyo street Japan 🇯🇵'
    textarea = await frame.J('textarea')
    await textarea.type(text)
    assert await retrieve_textarea_value(frame) == text


@sync
async def test_presses_meta_key(isolated_page, firefox):
    await isolated_page.evaluate(
        '''() => {
        window.result = null;
        document.addEventListener('keydown', event => {
            window.result = [event.key, event.code, event.metaKey];
        });
    }'''
    )
    await isolated_page.keyboard.press('Meta')
    key, code, metaKey = await isolated_page.evaluate('window.result')
    if firefox:
        assert key == 'OS'
        assert code == 'OSLeft'
        assert metaKey is False
    else:
        assert key == 'Meta'
        assert code == 'MetaLeft'
        assert metaKey
