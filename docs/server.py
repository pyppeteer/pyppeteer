#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os import path
import subprocess

from livereload import Server

docsdir = path.dirname(path.abspath(__file__))
builddir = path.join(docsdir, '_build')
build_cmd = [
    'sphinx-build', '-b', 'html', '-E', '-q', '-j', '4',
    '-d', path.join(builddir, 'doctrees'),
    docsdir, path.join(builddir, 'html'),
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


# Wtach documets
server.watch(docs('*.rst'), cmd, delay=1)
server.watch(docs('../*.rst'), cmd, delay=1)
server.watch(docs('*.md'), cmd, delay=1)
server.watch(docs('*/*.rst'), cmd, delay=1)
server.watch(docs('*/*.md'), cmd, delay=1)
server.watch(docs('*/*/*.rst'), cmd, delay=1)
server.watch(docs('*/*/*.md'), cmd, delay=1)

# Watch template/style
server.watch(docs('_templates/*.html'), cmd, delay=1)
server.watch(docs('_static/*.css'), cmd, delay=1)
server.watch(docs('_static/*.js'), cmd, delay=1)

# Watch theme
server.watch(docs('themes/slex/static/*.css_t'), cmd, delay=1)
server.watch(docs('themes/slex/*.html'), cmd, delay=1)
server.watch(docs('themes/slex/theme.conf'), cmd, delay=1)

# Watch package
server.watch(docs('../pyppeteer/*.py'), cmd, delay=1)
server.watch(docs('../pyppeteer/*/*.py'), cmd, delay=1)
server.watch(docs('../pyppeteer/*/*/*.py'), cmd, delay=1)

server.serve(port=8889, root=docs('_build/html'), debug=True, restart_delay=1)
