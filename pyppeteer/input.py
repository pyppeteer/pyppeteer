#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Keyboard and Mouse module."""

import asyncio
from typing import Any, Dict, TYPE_CHECKING

from pyppeteer.connection import Session

if TYPE_CHECKING:
    from typing import Set  # noqa: F401


class Keyboard(object):
    """Keyboard class."""

    def __init__(self, client: Session) -> None:
        """Make new keyboard object."""
        self._client = client
        self._modifiers = 0
        self._pressedKeys: Set[str] = set()

    async def down(self, key: str, options: dict = None, **kwargs: Any
                   ) -> None:
        """Press down key."""
        options = options or dict()
        options.update(kwargs)
        text = options.get('text')
        self._pressedKeys.add(key)
        self._modifiers |= self._modifierBit(key)
        config = {
            'type': 'rawKeyDown',
            'modifiers': self._modifiers,
            'windowsVirtualKeyCode': codeForKey(key),
            'key': key,
        }
        if text:
            config['type'] = 'keyDown'
            config['text'] = text
            config['unmodifiedText'] = text
        if 'autoRepeat' in self._pressedKeys:
            config['autoRepeat'] = True

        await self._client.send('Input.dispatchKeyEvent', config)

    def _modifierBit(self, key: str) -> int:
        if key == 'Alt':
            return 1
        if key == 'Control':
            return 2
        if key == 'Meta':
            return 4
        if key == 'Shift':
            return 8
        return 0

    async def up(self, key: str) -> None:
        """Up pressed key."""
        self._modifiers &= not self._modifierBit(key)
        self._pressedKeys.remove(key)
        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'keyUp',
            'modifiers': self._modifiers,
            'key': key,
            'windowsVirtualKeyCode': codeForKey(key),
        })

    async def sendCharacter(self, char: str) -> None:
        """Send character."""
        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'char',
            'modifiers': self._modifiers,
            'text': char,
            'key': char,
            'unmodifiedText': char,
        })

    async def type(self, text: str, options: Dict) -> None:
        """Type characters."""
        delay = 0
        if options and options.get('delay'):
            delay = options['delay']
        for char in text:
            await self.press(char, {'text': char, 'delay': delay})
            if delay:
                await asyncio.sleep(delay / 1000)

    async def press(self, key: str, options: Dict) -> None:
        """Press key."""
        await self.down(key, options)
        if options and options.get('delay'):
            await asyncio.sleep(options['delay'] / 1000)
        await self.up(key)


class Mouse(object):
    """Mouse class."""

    def __init__(self, client: Session, keyboard: Keyboard) -> None:
        """Make new mouse object."""
        self._client = client
        self._keyboard = keyboard
        self._x = 0.0
        self._y = 0.0
        self._button = 'none'

    async def move(self, x: float, y: float, options: dict = None,
                   **kwargs: Any) -> None:
        """Move cursor."""
        options = options or dict()
        options.update(kwargs)
        fromX = self._x
        fromY = self._y
        self._x = x
        self._y = y
        steps = options.get('steps', 1)
        for i in range(1, steps + 1):
            x = round(fromX + (self._x - fromX) * (i / steps))
            y = round(fromY + (self._y - fromY) * (i / steps))
            await self._client.send('Input.dispatchMouseEvent', {
                'type': 'mouseMoved',
                'button': self._button,
                'x': x,
                'y': y,
                'modifiers': self._keyboard._modifiers,
            })

    async def click(self, x: float, y: float, options: dict = None,
                    **kwargs: Any) -> None:
        """Click button at (x, y)."""
        if options is None:
            options = dict()
        options.update(kwargs)
        await self.move(x, y)
        await self.down(options)
        if options and options.get('delay'):
            await asyncio.sleep(options.get('delay', 0))
        await self.up(options)

    async def down(self, options: dict = None, **kwargs: Any) -> None:
        """Press down button."""
        if options is None:
            options = dict()
        options.update(kwargs)
        self._button = options.get('button', 'left')
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mousePressed',
            'button': self._button,
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
        })

    async def up(self, options: dict = None, **kwargs: Any) -> None:
        """Up pressed button."""
        if options is None:
            options = dict()
        options.update(kwargs)
        self._button = 'none'
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mouseReleased',
            'button': options.get('button', 'left'),
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
        })


class Touchscreen(object):
    """Touchscreen class."""

    def __init__(self, client: Session, keyboard: Keyboard) -> None:
        """Make new touchscreen object."""
        self._client = client
        self._keyboard = keyboard

    async def tap(self, x: float, y: float) -> None:
        """Tap (x, y)."""
        touchPoints = [{'x': round(x), 'y': round(y)}]
        await self._client.send('Input.dispatchTouchEvent', {
            'type': 'touchStart',
            'touchPoints': touchPoints,
            'modifiers': self._keyboard._modifiers,
        })
        await self._client.send('Input.dispatchTouchEvent', {
            'type': 'touchEnd',
            'touchPoints': [],
            'modifiers': self._keyboard._modifiers,
        })


keys = {
  'Cancel': 3,
  'Help': 6,
  'Backspace': 8,
  'Tab': 9,
  'Clear': 12,
  'Enter': 13,
  'Shift': 16,
  'Control': 17,
  'Alt': 18,
  'Pause': 19,
  'CapsLock': 20,
  'Escape': 27,
  'Convert': 28,
  'NonConvert': 29,
  'Accept': 30,
  'ModeChange': 31,
  'PageUp': 33,
  'PageDown': 34,
  'End': 35,
  'Home': 36,
  'ArrowLeft': 37,
  'ArrowUp': 38,
  'ArrowRight': 39,
  'ArrowDown': 40,
  'Select': 41,
  'Print': 42,
  'Execute': 43,
  'PrintScreen': 44,
  'Insert': 45,
  'Delete': 46,
  ')': 48,
  '!': 49,
  '@': 50,
  '#': 51,
  '$': 52,
  '%': 53,
  '^': 54,
  '&': 55,
  '*': 56,
  '(': 57,
  'Meta': 91,
  'ContextMenu': 93,
  'F1': 112,
  'F2': 113,
  'F3': 114,
  'F4': 115,
  'F5': 116,
  'F6': 117,
  'F7': 118,
  'F8': 119,
  'F9': 120,
  'F10': 121,
  'F11': 122,
  'F12': 123,
  'F13': 124,
  'F14': 125,
  'F15': 126,
  'F16': 127,
  'F17': 128,
  'F18': 129,
  'F19': 130,
  'F20': 131,
  'F21': 132,
  'F22': 133,
  'F23': 134,
  'F24': 135,
  'NumLock': 144,
  'ScrollLock': 145,
  'AudioVolumeMute': 173,
  'AudioVolumeDown': 174,
  'AudioVolumeUp': 175,
  'MediaTrackNext': 176,
  'MediaTrackPrevious': 177,
  'MediaStop': 178,
  'MediaPlayPause': 179,
  ';': 186,
  ':': 186,
  '=': 187,
  '+': 187,
  ',': 188,
  '<': 188,
  '-': 189,
  '_': 189,
  '.': 190,
  '>': 190,
  '/': 191,
  '?': 191,
  '`': 192,
  '~': 192,
  '[': 219,
  '{': 219,
  '\\': 220,
  '|': 220,
  ']': 221,
  '}': 221,
  '\'': 222,
  '"': 222,
  'AltGraph': 225,
  'Attn': 246,
  'CrSel': 247,
  'ExSel': 248,
  'EraseEof': 249,
  'Play': 250,
  'ZoomOut': 251
}


def codeForKey(key: str) -> int:
    """Get code for key."""
    if keys.get(key):
        return keys[key]
    if len(key) == 1:
        return ord(key.upper())
    return 0
