#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import unittest

from syncer import sync

from pyppeteer.errors import PageError, PyppeteerError

from base import BaseTestCase


class TestClick(BaseTestCase):
    @sync
    async def test_click(self):
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')

    @sync
    async def test_click_events(self):
        await self.page.goto(self.url + 'static/checkbox.html')
        self.assertIsNone(await self.page.evaluate('result.check'))
        await self.page.click('input#agree')
        self.assertTrue(await self.page.evaluate('result.check'))
        events = await self.page.evaluate('result.events')
        self.assertEqual(events, [
            'mouseover',
            'mouseenter',
            'mousemove',
            'mousedown',
            'mouseup',
            'click',
            'input',
            'change',
        ])
        await self.page.click('input#agree')
        self.assertEqual(await self.page.evaluate('result.check'), False)

    @sync
    async def test_click_label(self):
        await self.page.goto(self.url + 'static/checkbox.html')
        self.assertIsNone(await self.page.evaluate('result.check'))
        await self.page.click('label[for="agree"]')
        self.assertTrue(await self.page.evaluate('result.check'))
        events = await self.page.evaluate('result.events')
        self.assertEqual(events, [
            'click',
            'input',
            'change',
        ])
        await self.page.click('label[for="agree"]')
        self.assertEqual(await self.page.evaluate('result.check'), False)

    @sync
    async def test_click_fail(self):
        await self.page.goto(self.url + 'static/button.html')
        with self.assertRaises(PageError) as cm:
            await self.page.click('button.does-not-exist')
        self.assertEqual(
            'No node found for selector: button.does-not-exist',
            cm.exception.args[0],
        )

    @sync
    async def test_touch_enabled_viewport(self):
        await self.page.setViewport({
            'width': 375,
            'height': 667,
            'deviceScaleFactor': 2,
            'isMobile': True,
            'hasTouch': True,
            'isLandscape': False,
        })
        await self.page.mouse.down()
        await self.page.mouse.move(100, 10)
        await self.page.mouse.up()

    @sync
    async def test_click_after_navigation(self):
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        await self.page.goto(self.url + 'static/button.html')
        await self.page.click('button')
        self.assertEqual(await self.page.evaluate('result'), 'Clicked')


class TestFileUpload(BaseTestCase):
    @sync
    async def test_file_upload(self):
        await self.page.goto(self.url + 'static/fileupload.html')
        filePath = Path(__file__).parent / 'file-to-upload.txt'
        input = await self.page.J('input')
        await input.uploadFile(str(filePath))
        self.assertEqual(
            await self.page.evaluate('e => e.files[0].name', input),
            'file-to-upload.txt',
        )
        self.assertEqual(
            await self.page.evaluate('''e => {
                const reader = new FileReader();
                const promise = new Promise(fulfill => reader.onload = fulfill);
                reader.readAsText(e.files[0]);
                return promise.then(() => reader.result);
            }''', input),  # noqa: E501
            'contents of the file\n',
        )

    @sync
    async def test_resize_textarea(self):
        await self.page.goto(self.url + 'static/textarea.html')
        get_dimensions = '''
    function () {
      const rect = document.querySelector('textarea').getBoundingClientRect();
      return {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height
      };
    }
        '''

        dimensions = await self.page.evaluate(get_dimensions)
        x = dimensions['x']
        y = dimensions['y']
        width = dimensions['width']
        height = dimensions['height']
        mouse = self.page.mouse
        await mouse.move(x + width - 4, y + height - 4)
        await mouse.down()
        await mouse.move(x + width + 100, y + height + 100)
        await mouse.up()
        new_dimensions = await self.page.evaluate(get_dimensions)
        self.assertEqual(new_dimensions['width'], width + 104)
        self.assertEqual(new_dimensions['height'], height + 104)


class TestType(BaseTestCase):
    @sync
    async def test_key_type(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        text = 'Type in this text!'
        await textarea.type(text)
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, text)
        result = await self.page.evaluate('() => result')
        self.assertEqual(result, text)

    @sync
    async def test_key_arrowkey(self):
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.type('textarea', 'Hello World!')
        for char in 'World!':
            await self.page.keyboard.press('ArrowLeft')
        await self.page.keyboard.type('inserted ')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'Hello inserted World!')

        await self.page.keyboard.down('Shift')
        for char in 'inserted ':
            await self.page.keyboard.press('ArrowLeft')
        await self.page.keyboard.up('Shift')
        await self.page.keyboard.press('Backspace')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'Hello World!')

    @sync
    async def test_key_press_element_handle(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        await textarea.press('a', text='f')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, 'f')

        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => e.preventDefault(), true)'  # noqa: E501
        )
        await textarea.press('a', text='y')
        self.assertEqual(result, 'f')

    @sync
    async def test_key_send_char(self):
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.focus('textarea')
        await self.page.keyboard.sendCharacter('朝')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, '朝')

        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => e.preventDefault(), true)'  # noqa: E501
        )
        await self.page.keyboard.sendCharacter('a')
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, '朝a')

    @sync
    async def test_repeat_shift_key(self):
        await self.page.goto(self.url + 'static/keyboard.html')
        keyboard = self.page.keyboard
        codeForKey = {'Shift': 16, 'Alt': 18, 'Meta': 91, 'Control': 17}
        for key, code in codeForKey.items():
            await keyboard.down(key)
            self.assertEqual(
                await self.page.evaluate('getResult()'),
                'Keydown: {key} {key}Left {code} [{key}]'.format(
                    key=key, code=code),
            )
            await keyboard.down('!')
            if key == 'Shift':
                self.assertEqual(
                    await self.page.evaluate('getResult()'),
                    'Keydown: ! Digit1 49 [{key}]\n'
                    'Keypress: ! Digit1 33 33 33 [{key}]'.format(key=key),
                )
            else:
                self.assertEqual(
                    await self.page.evaluate('getResult()'),
                    'Keydown: ! Digit1 49 [{key}]'.format(key=key),
                )
            await keyboard.up('!')
            self.assertEqual(
                await self.page.evaluate('getResult()'),
                'Keyup: ! Digit1 49 [{key}]'.format(key=key),
            )
            await keyboard.up(key)
            self.assertEqual(
                await self.page.evaluate('getResult()'),
                'Keyup: {key} {key}Left {code} []'.format(key=key, code=code),
            )

    @sync
    async def test_repeat_multiple_modifiers(self):
        await self.page.goto(self.url + 'static/keyboard.html')
        keyboard = self.page.keyboard
        await keyboard.down('Control')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: Control ControlLeft 17 [Control]',
        )
        await keyboard.down('Meta')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: Meta MetaLeft 91 [Control Meta]',
        )
        await keyboard.down(';')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: ; Semicolon 186 [Control Meta]',
        )
        await keyboard.up(';')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keyup: ; Semicolon 186 [Control Meta]',
        )
        await keyboard.up('Control')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keyup: Control ControlLeft 17 [Meta]',
        )
        await keyboard.up('Meta')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keyup: Meta MetaLeft 91 []',
        )

    @sync
    async def test_send_proper_code_while_typing(self):
        await self.page.goto(self.url + 'static/keyboard.html')
        await self.page.keyboard.type('!')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: ! Digit1 49 []\n'
            'Keypress: ! Digit1 33 33 33 []\n'
            'Keyup: ! Digit1 49 []'
        )
        await self.page.keyboard.type('^')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: ^ Digit6 54 []\n'
            'Keypress: ^ Digit6 94 94 94 []\n'
            'Keyup: ^ Digit6 54 []'
        )

    @sync
    async def test_send_proper_code_while_typing_with_shift(self):
        await self.page.goto(self.url + 'static/keyboard.html')
        await self.page.keyboard.down('Shift')
        await self.page.keyboard.type('~')
        self.assertEqual(
            await self.page.evaluate('getResult()'),
            'Keydown: Shift ShiftLeft 16 [Shift]\n'
            'Keydown: ~ Backquote 192 [Shift]\n'
            'Keypress: ~ Backquote 126 126 126 [Shift]\n'
            'Keyup: ~ Backquote 192 [Shift]'
        )
        await self.page.keyboard.up('Shift')

    @sync
    async def test_not_type_prevent_events(self) -> None:
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.focus('textarea')
        await self.page.evaluate('''
window.addEventListener('keydown', event => {
    event.stopPropagation();
    event.stopImmediatePropagation();
    if (event.key === 'l')
        event.preventDefault();
    if (event.key === 'o')
        Promise.resolve().then(() => event.preventDefault());
}, false);''', force_expr=True)
        await self.page.keyboard.type('Hello World!')
        self.assertEqual(await self.page.evaluate('textarea.value'), 'He Wrd!')

    @sync
    async def test_key_modifiers(self):
        keyboard = self.page.keyboard
        self.assertEqual(keyboard._modifiers, 0)
        await keyboard.down('Shift')
        self.assertEqual(keyboard._modifiers, 8)
        await keyboard.down('Alt')
        self.assertEqual(keyboard._modifiers, 9)
        await keyboard.up('Shift')
        self.assertEqual(keyboard._modifiers, 1)
        await keyboard.up('Alt')
        self.assertEqual(keyboard._modifiers, 0)

    @unittest.skip('Cannot pass this test')
    @sync
    async def test_repeat_properly(self):
        await self.page.goto(self.url + 'static/textarea.html')
        await self.page.focus('textarea')
        await self.page.evaluate(
            'document.querySelector("textarea").addEventListener("keydown",'
            '    e => window.lastEvent = e, true)', force_expr=True,
        )
        await self.page.keyboard.down('a', {'text': 'a'})
        self.assertFalse(await self.page.evaluate('window.lastEvent.repeat'))
        await self.page.keyboard.press('a')
        self.assertTrue(await self.page.evaluate('window.lastEvent.repeat'))

    @sync
    async def test_key_type_long(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        text = 'This text is two lines.\\nThis is character 朝.'
        await textarea.type(text)
        result = await self.page.evaluate(
            '() => document.querySelector("textarea").value'
        )
        self.assertEqual(result, text)
        result = await self.page.evaluate('() => result')
        self.assertEqual(result, text)

    @sync
    async def test_key_location(self):
        await self.page.goto(self.url + 'static/textarea.html')
        textarea = await self.page.J('textarea')
        await self.page.evaluate(
            '() => window.addEventListener("keydown", e => window.keyLocation = e.location, true)'  # noqa: E501
        )

        await textarea.press('Digit5')
        self.assertEqual(await self.page.evaluate('keyLocation'), 0)

        await textarea.press('ControlLeft')
        self.assertEqual(await self.page.evaluate('keyLocation'), 1)

        await textarea.press('ControlRight')
        self.assertEqual(await self.page.evaluate('keyLocation'), 2)

        await textarea.press('NumpadSubtract')
        self.assertEqual(await self.page.evaluate('keyLocation'), 3)

    @sync
    async def test_key_unknown(self):
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('NotARealKey')
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('ё')
        with self.assertRaises(PyppeteerError):
            await self.page.keyboard.press('😊')
