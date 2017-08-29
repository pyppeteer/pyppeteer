#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dialog module."""

from types import SimpleNamespace
from pyppeteer.connection import Session


class Dialog(object):
    """Dialog class."""

    Type = SimpleNamespace(
        Alert='alert',
        BeforeUnload='beforeunload',
        Confirm='confirm',
        Prompt='prompt',
    )

    def __init__(self, client: Session, type: str, message: str,
                 defaultValue: str = '') -> None:
        """Make new dialog."""
        self._client = client
        self._type = type
        self._message = message
        self._handled = False
        self._defalutValue = defaultValue

    def message(self) -> str:
        """Get dialog message."""
        return self._message

    def defaultValue(self) -> str:
        """Get default selected dialog value."""
        return self._defalutValue

    async def accept(self, promptText: str) -> None:
        """Accept the dialog."""
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
