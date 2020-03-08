#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

from syncer import sync

from .base import BaseTestCase


class TestDialog(BaseTestCase):
    @sync
    async def test_alert(self):
        def dialog_test(dialog):
            assert dialog.type == 'alert'
            assert dialog.defaultValue == ''
            assert dialog.message == 'yo'
            asyncio.ensure_future(dialog.accept())

        self.page.on('dialog', dialog_test)
        await self.page.evaluate('() => alert("yo")')

    @sync
    async def test_prompt(self):
        def dialog_test(dialog):
            assert dialog.type == 'prompt'
            assert dialog.defaultValue == 'yes.'
            assert dialog.message == 'question?'
            asyncio.ensure_future(dialog.accept('answer!'))

        self.page.on('dialog', dialog_test)
        answer = await self.page.evaluate('() => prompt("question?", "yes.")')
        assert answer == 'answer!'

    @sync
    async def test_prompt_dismiss(self):
        def dismiss_test(dialog, *args):
            asyncio.ensure_future(dialog.dismiss())

        self.page.on('dialog', dismiss_test)
        result = await self.page.evaluate('() => prompt("question?", "yes.")')
        assert result is None
