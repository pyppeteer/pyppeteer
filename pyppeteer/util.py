#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Utility functions."""

import gc
import socket
from typing import Dict, Optional

__all__ = [
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
