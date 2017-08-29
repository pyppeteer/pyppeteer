#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Keyboard and Mouse module."""

import asyncio
from typing import TYPE_CHECKING

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

    async def down(self, key: str, options: dict):
        """Press down key."""
        text = options.get('text')
        autoRepeat = key in self._pressedKeys
        self._pressedKeys.add(key)
        self._modifiers |= self._modifierBit(key)

        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'keyDown' if text else 'rawKeyDown',
            'modifiers': self._modifiers,
            'windowsVirtualKeyCode': codeForKey(key),
            'key': key,
            'text': text,
            'unmodifiedText': text,
            'autoRepeat': autoRepeat,
        })

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


class Mouse(object):
    """Mouse class."""

    def __init__(self, client: Session, keyboard: Keyboard) -> None:
        """Make new mouse object."""
        self._client = client
        self._keyboard = keyboard
        self._x = 0
        self._y = 0
        self._button = 'none'

    async def move(self, x: int, y: int) -> None:
        """Move cursor."""
        self._x = x
        self._y = y
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mouseMoved',
            'button': self._button,
            'x': x,
            'y': y,
            'modifiers': self._keyboard._modifiers,
        })

    async def click(self, x: int, y: int, options: dict = None) -> None:
        """Click button at (x, y)."""
        if options is None:
            options = dict()
        await self.move(x, y)
        await self.down(options)
        if options and options.get('delay'):
            await asyncio.sleep(options.get('delay', 0))
        await self.up(options)

    async def down(self, options: dict = None) -> None:
        """Press down button."""
        if options is None:
            options = dict()
        self._button = options.get('button', 'left')
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mousePressed',
            'button': self._button,
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
        })

    async def up(self, options: dict = None) -> None:
        """Up pressed button."""
        if options is None:
            options = dict()
        self._button = 'none'
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mouseReleased',
            'button': options.get('button', 'left'),
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
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
