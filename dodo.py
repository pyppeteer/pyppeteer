#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Doit task definitions."""

DOIT_CONFIG = {
    'default_tasks': [
        'check',
    ],
    'continue': True,
    'verbosity': 1,
    'num_process': 8,
    'par_type': 'thread',
}


def task_flake8():
    """Run flake8 check."""
    return {
        'actions': ['flake8 setup.py pyppeteer tests'],
    }


def task_mypy():
    """Run mypy check."""
    return {
        'actions': ['mypy pyppeteer'],
    }


def task_pydocstyle():
    """Run docstyle check."""
    return {
        'actions': ['pydocstyle pyppeteer'],
    }


def task_docs():
    """Build sphinx document."""
    return {
        'actions': ['sphinx-build -q -W -E -j 4 -b html docs docs/_build/html'],
    }


def task_check():
    """Run flake8/mypy/pydocstyle/docs tasks."""
    return {
        'actions': None,
        'task_dep': ['flake8', 'mypy', 'pydocstyle', 'docs']
    }
