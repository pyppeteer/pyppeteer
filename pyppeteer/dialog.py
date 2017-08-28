#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from types import SimpleNamespace
from pyppeteer.connection import Session


class Dialog(object):
    Type = SimpleNamespace(
        Alert='alert',
        BeforeUnload='beforeunload',
        Confirm='confirm',
        Prompt='prompt',
    )

    def __init__(self, client: Session, type: str, message: str,
                 defaultValue: str = '') -> None:
        self._client = client
        self._type = type
        self._message = message
        self._handled = False
        self._defalutValue = defaultValue

    def message(self) -> str:
        return self._message

    def defaultValue(self) -> str:
        return self._defalutValue

    async def accept(self, promptText: str) -> None:
        self._handled = True
        await self._client.send('Page.handleJavaScriptDialog', {
            'accept': True,
            'promptText': promptText,
        })

    async def dismiss(self) -> None:
        self._handled = True
        await self._client.send('Page.handleJavaScriptDialog', {
            'accept': False,
        })
