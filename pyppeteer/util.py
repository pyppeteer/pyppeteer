#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gc
import socket

from pyppeteer.chromium_downloader import check_chromium, chromium_excutable
from pyppeteer.chromium_downloader import download_chromium

__all__ = [
    'check_chromium',
    'chromium_excutable',
    'download_chromium',
    'install_asyncio',
    'get_free_port',
]


def install_asyncio() -> None:
    try:
        from tornado.ioloop import IOLoop
        from tornado.platform.asyncio import AsyncIOMainLoop
        if not IOLoop.initialized():
            AsyncIOMainLoop().install()
    except ImportError:
        pass


def get_free_port() -> int:
    sock = socket.socket()
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    del sock
    gc.collect()
    return port
