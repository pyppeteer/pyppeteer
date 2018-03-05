#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Utitlity functions."""

import gc
import socket
from typing import Dict, Optional

from pyppeteer.chromium_downloader import check_chromium, chromium_excutable
from pyppeteer.chromium_downloader import download_chromium

__all__ = [
    'check_chromium',
    'chromium_excutable',
    'download_chromium',
    'get_free_port',
]


def get_free_port() -> int:
    """Get free port."""
    sock = socket.socket()
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    del sock
    gc.collect()
    return port


def merge_dict(dict1: Optional[Dict], dict2: Optional[Dict]) -> Dict:
    new_dict = {}
    if dict1:
        new_dict.update(dict1)
    if dict2:
        new_dict.update(dict2)
    return new_dict
