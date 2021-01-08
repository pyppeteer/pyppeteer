#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from syncer import sync


class TestDialog:
    @sync
    async def test_fires(self, isolated_page):
        def dialog_test(dialog):
            assert dialog.type == 'alert'
            assert dialog.defaultValue == ''
            assert dialog.message == 'yo'
            asyncio.ensure_future(dialog.accept())

        isolated_page.on('dialog', dialog_test)
        await isolated_page.evaluate('() => alert("yo")')

    @sync
    async def test_accepting_prompt(self, isolated_page):
        def dialog_test(dialog):
            assert dialog.type == 'prompt'
            assert dialog.defaultValue == 'yes.'
            assert dialog.message == 'question?'
            asyncio.ensure_future(dialog.accept('answer!'))

        isolated_page.on('dialog', dialog_test)
        answer = await isolated_page.evaluate('() => prompt("question?", "yes.")')
        assert answer == 'answer!'

    @sync
    async def test_prompt_dismiss(self, isolated_page):
        def dismiss_test(dialog, *_):
            asyncio.create_task(dialog.dismiss())

        isolated_page.on('dialog', dismiss_test)
        result = await isolated_page.evaluate('() => prompt("question?")')
        assert result is None
