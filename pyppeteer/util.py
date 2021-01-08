#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Utility functions."""

import gc
import socket


def get_free_port() -> int:
    """Get free port."""
    sock = socket.socket()
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    del sock
    gc.collect()
    return port
