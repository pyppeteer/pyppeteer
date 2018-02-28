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
        if text is None:
            text = key if len(key) == 1 and not self._modifiers & ~8 else ''
        self._pressedKeys.add(key)
        self._modifiers |= self._modifierBit(key)
        config = {
            'type': 'rawKeyDown',
            'modifiers': self._modifiers,
            'windowsVirtualKeyCode': keyCodeForKey(key),
            'code': codeForKey(key),
            'key': key,
            'text': text,
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
            'windowsVirtualKeyCode': keyCodeForKey(key),
            'code': codeForKey(key),
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
  'Cancel': {'keyCode': 3, 'code': 'Abort'},
  'Help': {'keyCode': 6, 'code': 'Help'},
  'Backspace': {'keyCode': 8, 'code': 'Backspace'},
  'Tab': {'keyCode': 9, 'code': 'Tab'},
  'Clear': {'keyCode': 12, 'code': ''},
  'Enter': {'keyCode': 13, 'code': 'Enter'},
  'Shift': {'keyCode': 16, 'code': 'ShiftLeft'},
  'Control': {'keyCode': 17, 'code': 'ControlLeft'},
  'Alt': {'keyCode': 18, 'code': 'AltLeft'},
  'Pause': {'keyCode': 19, 'code': 'Pause'},
  'CapsLock': {'keyCode': 20, 'code': 'CapsLock'},
  'Escape': {'keyCode': 27, 'code': 'Escape'},
  'Convert': {'keyCode': 28, 'code': 'Convert'},
  'NonConvert': {'keyCode': 29, 'code': 'NonConvert'},
  'Accept': {'keyCode': 30, 'code': ''},
  'ModeChange': {'keyCode': 31, 'code': ''},
  'PageUp': {'keyCode': 33, 'code': 'PageUp'},
  'PageDown': {'keyCode': 34, 'code': 'PageDown'},
  'End': {'keyCode': 35, 'code': 'End'},
  'Home': {'keyCode': 36, 'code': 'Home'},
  'ArrowLeft': {'keyCode': 37, 'code': 'ArrowLeft'},
  'ArrowUp': {'keyCode': 38, 'code': 'ArrowUp'},
  'ArrowRight': {'keyCode': 39, 'code': 'ArrowRight'},
  'ArrowDown': {'keyCode': 40, 'code': 'ArrowDown'},
  'Select': {'keyCode': 41, 'code': 'Select'},
  'Print': {'keyCode': 42, 'code': ''},
  'Execute': {'keyCode': 43, 'code': 'Open'},
  'PrintScreen': {'keyCode': 44, 'code': 'PrintScreen'},
  'Insert': {'keyCode': 45, 'code': 'Insert'},
  'Delete': {'keyCode': 46, 'code': 'Delete'},
  ')': {'keyCode': 48, 'code': 'Digit0'},
  '!': {'keyCode': 49, 'code': 'Digit1'},
  '@': {'keyCode': 50, 'code': 'Digit2'},
  '#': {'keyCode': 51, 'code': 'Digit3'},
  '$': {'keyCode': 52, 'code': 'Digit4'},
  '%': {'keyCode': 53, 'code': 'Digit5'},
  '^': {'keyCode': 54, 'code': 'Digit6'},
  '&': {'keyCode': 55, 'code': 'Digit7'},
  '*': {'keyCode': 56, 'code': 'Digit8'},
  '(': {'keyCode': 57, 'code': 'Digit9'},
  'Meta': {'keyCode': 91, 'code': 'MetaLeft'},
  'ContextMenu': {'keyCode': 93, 'code': 'ContextMenu'},
  'F1': {'keyCode': 112, 'code': 'F1'},
  'F2': {'keyCode': 113, 'code': 'F2'},
  'F3': {'keyCode': 114, 'code': 'F3'},
  'F4': {'keyCode': 115, 'code': 'F4'},
  'F5': {'keyCode': 116, 'code': 'F5'},
  'F6': {'keyCode': 117, 'code': 'F6'},
  'F7': {'keyCode': 118, 'code': 'F7'},
  'F8': {'keyCode': 119, 'code': 'F8'},
  'F9': {'keyCode': 120, 'code': 'F9'},
  'F10': {'keyCode': 121, 'code': 'F10'},
  'F11': {'keyCode': 122, 'code': 'F11'},
  'F12': {'keyCode': 123, 'code': 'F12'},
  'F13': {'keyCode': 124, 'code': 'F13'},
  'F14': {'keyCode': 125, 'code': 'F14'},
  'F15': {'keyCode': 126, 'code': 'F15'},
  'F16': {'keyCode': 127, 'code': 'F16'},
  'F17': {'keyCode': 128, 'code': 'F17'},
  'F18': {'keyCode': 129, 'code': 'F18'},
  'F19': {'keyCode': 130, 'code': 'F19'},
  'F20': {'keyCode': 131, 'code': 'F20'},
  'F21': {'keyCode': 132, 'code': 'F21'},
  'F22': {'keyCode': 133, 'code': 'F22'},
  'F23': {'keyCode': 134, 'code': 'F23'},
  'F24': {'keyCode': 135, 'code': 'F24'},
  'NumLock': {'keyCode': 144, 'code': 'NumLock'},
  'ScrollLock': {'keyCode': 145, 'code': 'ScrollLock'},
  'AudioVolumeMute': {'keyCode': 173, 'code': 'AudioVolumeMute'},
  'AudioVolumeDown': {'keyCode': 174, 'code': 'AudioVolumeDown'},
  'AudioVolumeUp': {'keyCode': 175, 'code': 'AudioVolumeUp'},
  'MediaTrackNext': {'keyCode': 176, 'code': 'MediaTrackNext'},
  'MediaTrackPrevious': {'keyCode': 177, 'code': 'MediaTrackPrevious'},
  'MediaStop': {'keyCode': 178, 'code': 'MediaStop'},
  'MediaPlayPause': {'keyCode': 179, 'code': 'MediaPlayPause'},
  ';': {'keyCode': 186, 'code': 'Semicolon'},
  ':': {'keyCode': 186, 'code': 'Semicolon'},
  '=': {'keyCode': 187, 'code': 'Equal'},
  '+': {'keyCode': 187, 'code': 'Equal'},
  ',': {'keyCode': 188, 'code': 'Comma'},
  '<': {'keyCode': 188, 'code': 'Comma'},
  '-': {'keyCode': 189, 'code': 'Minus'},
  '_': {'keyCode': 189, 'code': 'Minus'},
  '.': {'keyCode': 190, 'code': 'Period'},
  '>': {'keyCode': 190, 'code': 'Period'},
  '/': {'keyCode': 191, 'code': 'Slash'},
  '?': {'keyCode': 191, 'code': 'Slash'},
  '`': {'keyCode': 192, 'code': 'Backquote'},
  '~': {'keyCode': 192, 'code': 'Backquote'},
  '[': {'keyCode': 219, 'code': 'BracketLeft'},
  '{': {'keyCode': 219, 'code': 'BracketLeft'},
  '\\': {'keyCode': 220, 'code': 'Backslash'},
  '|': {'keyCode': 220, 'code': 'Backslash'},
  ']': {'keyCode': 221, 'code': 'BracketRight'},
  '}': {'keyCode': 221, 'code': 'BracketRight'},
  '\'': {'keyCode': 222, 'code': 'Quote'},
  '"': {'keyCode': 222, 'code': 'Quote'},
  'AltGraph': {'keyCode': 225, 'code': 'AltGraph'},
  'Attn': {'keyCode': 246, 'code': ''},
  'CrSel': {'keyCode': 247, 'code': 'Props'},
  'ExSel': {'keyCode': 248, 'code': ''},
  'EraseEof': {'keyCode': 249, 'code': ''},
  'Play': {'keyCode': 250, 'code': ''},
  'ZoomOut': {'keyCode': 251, 'code': ''},
  '0': {'keyCode': 48, 'code': 'Digit0'},
  '1': {'keyCode': 49, 'code': 'Digit1'},
  '2': {'keyCode': 50, 'code': 'Digit2'},
  '3': {'keyCode': 51, 'code': 'Digit3'},
  '4': {'keyCode': 52, 'code': 'Digit4'},
  '5': {'keyCode': 53, 'code': 'Digit5'},
  '6': {'keyCode': 54, 'code': 'Digit6'},
  '7': {'keyCode': 55, 'code': 'Digit7'},
  '8': {'keyCode': 56, 'code': 'Digit8'},
  '9': {'keyCode': 57, 'code': 'Digit9'},
  'q': {'keyCode': 81, 'code': 'KeyQ'},
  'w': {'keyCode': 87, 'code': 'KeyW'},
  'e': {'keyCode': 69, 'code': 'KeyE'},
  'r': {'keyCode': 82, 'code': 'KeyR'},
  't': {'keyCode': 84, 'code': 'KeyT'},
  'y': {'keyCode': 89, 'code': 'KeyY'},
  'u': {'keyCode': 85, 'code': 'KeyU'},
  'i': {'keyCode': 73, 'code': 'KeyI'},
  'o': {'keyCode': 79, 'code': 'KeyO'},
  'p': {'keyCode': 80, 'code': 'KeyP'},
  'a': {'keyCode': 65, 'code': 'KeyA'},
  's': {'keyCode': 83, 'code': 'KeyS'},
  'd': {'keyCode': 68, 'code': 'KeyD'},
  'f': {'keyCode': 70, 'code': 'KeyF'},
  'g': {'keyCode': 71, 'code': 'KeyG'},
  'h': {'keyCode': 72, 'code': 'KeyH'},
  'j': {'keyCode': 74, 'code': 'KeyJ'},
  'k': {'keyCode': 75, 'code': 'KeyK'},
  'l': {'keyCode': 76, 'code': 'KeyL'},
  'z': {'keyCode': 90, 'code': 'KeyZ'},
  'x': {'keyCode': 88, 'code': 'KeyX'},
  'c': {'keyCode': 67, 'code': 'KeyC'},
  'v': {'keyCode': 86, 'code': 'KeyV'},
  'b': {'keyCode': 66, 'code': 'KeyB'},
  'n': {'keyCode': 78, 'code': 'KeyN'},
  'm': {'keyCode': 77, 'code': 'KeyM'},
  'Q': {'keyCode': 81, 'code': 'KeyQ'},
  'W': {'keyCode': 87, 'code': 'KeyW'},
  'E': {'keyCode': 69, 'code': 'KeyE'},
  'R': {'keyCode': 82, 'code': 'KeyR'},
  'T': {'keyCode': 84, 'code': 'KeyT'},
  'Y': {'keyCode': 89, 'code': 'KeyY'},
  'U': {'keyCode': 85, 'code': 'KeyU'},
  'I': {'keyCode': 73, 'code': 'KeyI'},
  'O': {'keyCode': 79, 'code': 'KeyO'},
  'P': {'keyCode': 80, 'code': 'KeyP'},
  'A': {'keyCode': 65, 'code': 'KeyA'},
  'S': {'keyCode': 83, 'code': 'KeyS'},
  'D': {'keyCode': 68, 'code': 'KeyD'},
  'F': {'keyCode': 70, 'code': 'KeyF'},
  'G': {'keyCode': 71, 'code': 'KeyG'},
  'H': {'keyCode': 72, 'code': 'KeyH'},
  'J': {'keyCode': 74, 'code': 'KeyJ'},
  'K': {'keyCode': 75, 'code': 'KeyK'},
  'L': {'keyCode': 76, 'code': 'KeyL'},
  'Z': {'keyCode': 90, 'code': 'KeyZ'},
  'X': {'keyCode': 88, 'code': 'KeyX'},
  'C': {'keyCode': 67, 'code': 'KeyC'},
  'V': {'keyCode': 86, 'code': 'KeyV'},
  'B': {'keyCode': 66, 'code': 'KeyB'},
  'N': {'keyCode': 78, 'code': 'KeyN'},
  'M': {'keyCode': 77, 'code': 'KeyM'}
}


def keyCodeForKey(key: str) -> int:
    """Get key code for key."""
    if keys.get(key):
        return keys[key]['keyCode']  # type: ignore
    if len(key) == 1:
        return ord(key.upper())
    return 0


def codeForKey(key: str) -> str:
    """Get code for key."""
    if not keys.get(key):
        return ''
    return keys[key]['code']  # type: ignore
