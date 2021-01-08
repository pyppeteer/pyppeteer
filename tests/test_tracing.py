#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from pathlib import Path

import pytest
from pyppeteer.errors import NetworkError
from syncer import sync


@pytest.fixture
def temp_file_path(tmpdir):
    return Path(tmpdir / f'{time.perf_counter_ns()}file.json')


@sync
async def test_tracing(isolated_page, temp_file_path, server):
    await isolated_page.tracing.start(path=temp_file_path)
    await isolated_page.goto(server / 'grid.html')
    await isolated_page.tracing.stop()
    assert temp_file_path.is_file() and temp_file_path.stat().st_size > 0


@sync
async def test_custom_categories(isolated_page, temp_file_path):
    await isolated_page.tracing.start(path=temp_file_path, categories=['disabled-by-default-v8.cpu_profiler.hires'])
    await isolated_page.tracing.stop()
    assert temp_file_path.is_file() and temp_file_path.stat().st_size > 0
    trace_json = json.loads(temp_file_path.read_text())
    assert 'disabled-by-default-v8.cpu_profiler.hires' in trace_json['metadata']['trace-config']


@sync
async def test_two_page_error(isolated_page, shared_browser, temp_file_path):
    await isolated_page.tracing.start(path=temp_file_path)
    try:
        new_page = await shared_browser.newPage()
        with pytest.raises(NetworkError):
            await new_page.tracing.start(path=temp_file_path)
    finally:
        await new_page.close()
    await isolated_page.tracing.stop()


@sync
async def test_return_buffer(isolated_page, server, temp_file_path):
    await isolated_page.tracing.start(screenshots=True, path=temp_file_path)
    await isolated_page.goto(server / 'grid.html')
    trace = await isolated_page.tracing.stop()
    assert trace == temp_file_path.read_text()


@sync
async def test_works_without_any_options(isolated_page, server):
    await isolated_page.tracing.start()
    await isolated_page.goto(server / 'grid.html')
    trace = await isolated_page.tracing.stop()
    assert trace


@sync
@pytest.mark.skip(reason='No analogous python behaviour known')
async def test_return_null_on_error(isolated_page, server):
    await isolated_page.tracing.start(screenshots=True)
    await isolated_page.goto(server / 'grid.html')


@sync
async def test_without_path(isolated_page, server):
    await isolated_page.tracing.start(screenshots=True)
    await isolated_page.goto(server / 'grid.html')
    trace = await isolated_page.tracing.stop()
    assert 'screenshot' in trace
