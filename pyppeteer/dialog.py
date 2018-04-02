#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dialog module."""

from types import SimpleNamespace
from pyppeteer.connection import CDPSession


class Dialog(object):
    """Dialog class.

    Dialog objects are dispatched by page via the ``dialog`` event.
    """

    Type = SimpleNamespace(
        Alert='alert',
        BeforeUnload='beforeunload',
        Confirm='confirm',
        Prompt='prompt',
    )

    def __init__(self, client: CDPSession, type: str, message: str,
                 defaultValue: str = '') -> None:
        self._client = client
        self._type = type
        self._message = message
        self._handled = False
        self._defalutValue = defaultValue

    @property
    def type(self) -> str:
        """Get dialog type.

        One of ``alert``, ``beforeunload``, ``confirm``, or ``prompt``.
        """
        return self._type

    @property
    def message(self) -> str:
        """Get dialog message."""
        return self._message

    @property
    def defaultValue(self) -> str:
        """If dialog is prompt, get default prompt value.

        If dialog is not prompt, return empty string (``''``).
        """
        return self._defalutValue

    async def accept(self, promptText: str = '') -> None:
        """Accept the dialog.

        * ``promptText`` (str): A text to enter in prompt. If the dialog's type
          is not prompt, this does not cause any effect.
        """
        self._handled = True
        await self._client.send('Page.handleJavaScriptDialog', {
            'accept': True,
            'promptText': promptText,
        })

    async def dismiss(self) -> None:
        """Dismiss the dialog."""
        self._handled = True
        await self._client.send('Page.handleJavaScriptDialog', {
            'accept': False,
        })
