#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
from os import path

from livereload import Server, watcher

watcher.pyinotify = None  # disable pyinotify

docsdir = path.dirname(path.abspath(__file__))
builddir = path.join(docsdir, '_build')
build_cmd = [
    'sphinx-build',
    '-q',
    '-j',
    'auto',
    '-b',
    'html',
    '-d',
    path.join(builddir, 'doctrees'),
    docsdir,
    path.join(builddir, 'html'),
]


def cmd() -> None:
    print('=== Sphinx Build Start ===')
    subprocess.run(build_cmd, cwd=docsdir)
    print('=== Sphinx Build done ===')


# subprocess.run(['make', 'clean'], cwd=docsdir)
cmd()
server = Server()


def docs(p: str) -> str:
    return path.join(docsdir, p)


# Watch documents
server.watch(docs('*.py'), cmd, delay=1)
server.watch(docs('*.md'), cmd, delay=1)
server.watch(docs('../*.md'), cmd, delay=1)
server.watch(docs('*.md'), cmd, delay=1)
server.watch(docs('*/*.md'), cmd, delay=1)
server.watch(docs('*/*/*.md'), cmd, delay=1)

# Watch template/style
server.watch(docs('_templates/*.html'), cmd, delay=1)
server.watch(docs('_static/*.css'), cmd, delay=1)
server.watch(docs('_static/*.js'), cmd, delay=1)

# Watch package
server.watch(docs('../pyppeteer/*.py'), cmd, delay=1)
server.watch(docs('../pyppeteer/*/*.py'), cmd, delay=1)
server.watch(docs('../pyppeteer/*/*/*.py'), cmd, delay=1)

server.serve(port=8889, root=docs('_build/html'), debug=True, restart_delay=1)
