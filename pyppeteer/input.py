#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Keyboard and Mouse module

puppeteer equivalent: lib/Input.js
"""

import asyncio
from typing import TYPE_CHECKING, Dict

from pyppeteer.connection import CDPSession
from pyppeteer.errors import PyppeteerError
from pyppeteer.us_keyboard_layout import keyDefinitions

if TYPE_CHECKING:
    from typing import Set


class Keyboard:
    """Keyboard class provides as api for managing a virtual keyboard.

    The high level api is :meth:`type`, which takes raw characters and
    generate proper keydown, keypress/input, and keyup events on your page.

    For finer control, you can use :meth:`down`, :meth:`up`, and
    :meth:`sendCharacter` to manually fire events as if they were generated
    from a real keyboard.

    An example of holding down ``Shift`` in order to select and delete some
    text:

    .. code::

        await page.keyboard.type('Hello, World!')
        await page.keyboard.press('ArrowLeft')

        await page.keyboard.down('Shift')
        for i in ' World':
            await page.keyboard.press('ArrowLeft')
        await page.keyboard.up('Shift')

        await page.keyboard.press('Backspace')
        # Result text will end up saying 'Hello!'.

    An example of pressing ``A``:

    .. code::

        await page.keyboard.down('Shift')
        await page.keyboard.press('KeyA')
        await page.keyboard.up('Shift')
    """

    def __init__(self, client: CDPSession) -> None:
        self._client = client
        self._modifiers = 0
        self._pressedKeys: Set[str] = set()

    async def down(self, key: str, text: str = None) -> None:
        """Dispatch a ``keydown`` event with ``key``.

        If ``key`` is a single character and no modifier keys besides ``Shift``
        are being held down, and a ``keypress``/``input`` event will also
        generated. The ``text`` option can be specified to force an ``input``
        event to be generated.

        If ``key`` is a modifier key, like ``Shift``, ``Meta``, or ``Alt``,
        subsequent key presses will be sent with that modifier active. To
        release the modifier key, use :meth:`up` method.

        :arg key: Name of key to press, such as ``ArrowLeft``.
        :arg text: generate an input event with this text.

        .. note::
            Modifier keys DO influence :meth:`down`. Holding down ``shift``
            will type the text in upper case.
        """

        description = self._keyDescriptionForString(key)
        autoRepeat = description['code'] in self._pressedKeys
        self._pressedKeys.add(description['code'])
        self._modifiers |= self._modifierBit(description['key'])

        text = text or description['text']

        await self._client.send(
            'Input.dispatchKeyEvent',
            {
                'type': 'keyDown' if text else 'rawKeyDown',
                'modifiers': self._modifiers,
                'windowsVirtualKeyCode': description['keyCode'],
                'code': description['code'],
                'key': description['key'],
                'text': text,
                'unmodifiedText': text,
                'autoRepeat': autoRepeat,
                'location': description['location'],
                'isKeypad': description['location'] == 3,
            },
        )

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

    def _keyDescriptionForString(self, keyString: str) -> Dict:  # noqa: C901
        shift = self._modifiers & 8
        description = {
            'key': '',
            'keyCode': 0,
            'code': '',
            'text': '',
            'location': 0,
        }

        definition: Dict = keyDefinitions.get(keyString)  # type: ignore
        if not definition:
            raise PyppeteerError(f'Unknown key: "{keyString}"')

        if definition.get('key'):
            description['key'] = definition['key']
        if shift and definition.get('shiftKey'):
            description['key'] = definition['shiftKey']

        if definition.get('keyCode'):
            description['keyCode'] = definition['keyCode']
        if shift and definition.get('shiftKeyCode'):
            description['keyCode'] = definition['shiftKeyCode']

        if definition.get('code'):
            description['code'] = definition['code']

        if definition.get('location'):
            description['location'] = definition['location']

        if len(description['key']) == 1:  # type: ignore
            description['text'] = description['key']

        if definition.get('text'):
            description['text'] = definition['text']
        if shift and definition.get('shiftText'):
            description['text'] = definition['shiftText']

        # if any modifiers besides shift are pressed, no text should be sent
        if self._modifiers & ~8:
            description['text'] = ''

        return description

    async def up(self, key: str) -> None:
        """Dispatch a ``keyup`` event of the ``key``.

        :arg str key: Name of key to release, such as ``ArrowLeft``.
        """
        description = self._keyDescriptionForString(key)

        self._modifiers &= ~self._modifierBit(description['key'])
        if description['code'] in self._pressedKeys:
            self._pressedKeys.remove(description['code'])
        await self._client.send(
            'Input.dispatchKeyEvent',
            {
                'type': 'keyUp',
                'modifiers': self._modifiers,
                'key': description['key'],
                'windowsVirtualKeyCode': description['keyCode'],
                'code': description['code'],
                'location': description['location'],
            },
        )

    async def sendCharacter(self, char: str) -> None:
        """Send character into the page.

        This method dispatches a ``keypress`` and ``input`` event. This does
        not send a ``keydown`` or ``keyup`` event.

        .. note::
            Modifier keys DO NOT effect :meth:`sendCharacter`. Holding down
            ``shift`` will not type the text in upper case.
        """
        await self._client.send('Input.insertText', {'text': char})

    async def type(self, text: str, delay: float = 0) -> None:
        """Type characters into a focused element.

        This method sends ``keydown``, ``keypress``/``input``, and ``keyup``
        event for each character in the ``text``.

        To press a special key, like ``Control`` or ``ArrowDown``, use
        :meth:`press` method.

        :arg text: Text to type into a focused element.
        :arg delay: Specifies time to wait between key presses in milliseconds, defaults
          to 0.

        .. note::
            Modifier keys DO NOT effect :meth:`type`. Holding down ``shift``
            will not type the text in upper case.
        """
        for char in text:
            if char in keyDefinitions:
                await self.press(char, delay=delay)
            else:
                if delay:
                    await asyncio.sleep(delay / 1000)
                await self.sendCharacter(char)

    async def press(self, key: str, text: str = None, delay: float = 0) -> None:
        """Press ``key``.

        If ``key`` is a single character and no modifier keys besides
        ``Shift`` are being held down, a ``keypress``/``input`` event will also
        generated. The ``text`` option can be specified to force an input event
        to be generated.

        :arg key: Name of key to press, such as ``ArrowLeft``.
        :arg text: If specified, generates an input event with this
          text.
        :arg delay: Time to wait between ``keydown`` and
          ``keyup``. Defaults to 0.

        .. note::
            Modifier keys DO effect :meth:`press`. Holding down ``Shift`` will
            type the text in upper case.
        """

        await self.down(key, text)
        if delay:
            await asyncio.sleep(delay / 1000)
        await self.up(key)


class Mouse:
    """Mouse class.

    The :class:`Mouse` operates in main-frame CSS pixels relative to the
    top-left corner of the viewport.
    """

    def __init__(self, client: CDPSession, keyboard: Keyboard) -> None:
        self._client = client
        self._keyboard = keyboard
        self._x = 0.0
        self._y = 0.0
        self._button = 'none'

    async def move(self, x: float, y: float, steps: int = 1) -> None:
        """Move mouse cursor (dispatches a ``mousemove`` event).

        :arg x: x-coordinate to move to
        :arg y: y-coordinate to move to
        :arg steps: number of steps to break movement into
        """
        fromX = self._x
        fromY = self._y
        self._x = x
        self._y = y
        for i in range(1, steps + 1):
            await self._client.send(
                'Input.dispatchMouseEvent',
                {
                    'type': 'mouseMoved',
                    'button': self._button,
                    'x': round(fromX + (self._x - fromX) * (i / steps)),
                    'y': round(fromY + (self._y - fromY) * (i / steps)),
                    'modifiers': self._keyboard._modifiers,
                },
            )

    async def click(
        self, x: float, y: float, button: str = 'left', clickCount: int = 1, delay: float = 0, steps: int = 1,
    ) -> None:
        """Click mouse button at (``x``, ``y``).

        Shortcut to :meth:`move`, :meth:`down`, and :meth:`up`.

        :arg x: x coordinate to click
        :arg y: y coordinate to click
        :arg button: mouse button to use, one of ``left``, ``right``, or ``middle``, defaults to ``left``
        :arg clickCount: number of times to click, defaults to 1
        :arg delay: delay in ms between mouseDown and mouseUp events, defaults to 0
        :arg steps: steps to break mouse movement into, defaults to 1

        """
        await self.move(x, y, steps)
        await self.down(button, clickCount)
        if delay:
            await asyncio.sleep(delay / 1000)
        await self.up(button, clickCount)

    async def down(self, button: str = 'left', clickCount: int = 1) -> None:
        """Press mouse down

        :arg button: mouse button to use, one of ``left``, ``right``, or ``middle``, defaults to ``left``
        :arg clickCount: number of times to click, defaults to 1
        """
        self._button = button
        await self._client.send(
            'Input.dispatchMouseEvent',
            {
                'type': 'mousePressed',
                'button': self._button,
                'x': self._x,
                'y': self._y,
                'modifiers': self._keyboard._modifiers,
                'clickCount': clickCount,
            },
        )

    async def up(self, button: str = 'left', clickCount: int = 1) -> None:
        """Release pressed mouse

        :arg button: mouse button to use, one of ``left``, ``right``, or ``middle``, defaults to ``left``
        :arg clickCount: number of times to click, defaults to 1
        """
        self._button = 'none'
        await self._client.send(
            'Input.dispatchMouseEvent',
            {
                'type': 'mouseReleased',
                'button': button,
                'x': self._x,
                'y': self._y,
                'modifiers': self._keyboard._modifiers,
                'clickCount': clickCount,
            },
        )


class Touchscreen:
    """Touchscreen class."""

    def __init__(self, client: CDPSession, keyboard: Keyboard) -> None:
        """Make new touchscreen object."""
        self._client = client
        self._keyboard = keyboard

    async def tap(self, x: float, y: float) -> None:
        """Tap (``x``, ``y``).

        Dispatches a ``touchstart`` and ``touchend`` event.
        """
        # Touches appear to be lost during the first frame after navigation.
        # This waits a frame before sending the tap.
        # see https://crbug.com/613219
        await self._client.send(
            'Runtime.evaluate',
            {
                'expression': 'new Promise(x => requestAnimationFrame(() => requestAnimationFrame(x)))',
                'awaitPromise': True,
            },
        )

        touchPoints = [{'x': round(x), 'y': round(y)}]
        await self._client.send(
            'Input.dispatchTouchEvent',
            {'type': 'touchStart', 'touchPoints': touchPoints, 'modifiers': self._keyboard._modifiers,},
        )
        await self._client.send(
            'Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': [], 'modifiers': self._keyboard._modifiers,}
        )
