#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Doit task definitions."""

import multiprocessing

from doit.action import CmdAction

cores = multiprocessing.cpu_count()
DOIT_CONFIG = {
    'default_tasks': [
        'check',
    ],
    'continue': True,
    'verbosity': 1,
    'num_process': cores,
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
        'actions': [
            'sphinx-build -q -W -E -j auto -b html docs docs/_build/html',
        ],
    }


def task_readme():
    """Check long description for package."""
    return {
        'actions': ['python setup.py check -r -s'],
    }


def task_spell():
    """Check spelling of comments and docstrings."""
    return {
        'actions': [
            'pylint --disable all --enable spelling --spelling-dict en_US '
            '--spelling-private-dict-file spell.txt pyppeteer'
        ],
    }


def task_check():
    """Run flake8/mypy/pydocstyle/docs/readme tasks."""
    return {
        'actions': None,
        'task_dep': ['flake8', 'mypy', 'pydocstyle', 'docs', 'readme']
    }


def task_test():
    """Run pytest."""
    return {
        'actions': [CmdAction(
            'pytest -n {}'.format(cores // 2),
            buffering=1,
        )],
        'verbosity': 2,
    }


def task_all():
    """Run all tests and checks."""
    return {
        'actions': None,
        'task_dep': ['test', 'check'],
    }
