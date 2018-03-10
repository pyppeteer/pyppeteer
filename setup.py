#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path
from setuptools import setup
import sys

basedir = path.dirname(path.abspath(__file__))
extra_args = {}

if (3, 6) > sys.version_info >= (3, 5):
    in_dir = path.join(basedir, 'pyppeteer')
    out_dir = path.join(basedir, '.pyppeteer')
    packages = ['pyppeteer']
    package_dir = {'pyppeteer': '.pyppeteer'}
    if not path.exists(out_dir):
        if path.exists(in_dir):
            try:
                from py_backwards.compiler import compile_files
            except ImportError:
                import subprocess
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'py-backwards']
                )
                from py_backwards.compiler import compile_files
            target = (sys.version_info[0], sys.version_info[1])
            compile_files(in_dir, out_dir, target)
        else:
            raise Exception('Could not find package directory')
else:
    packages = ['pyppeteer']
    package_dir = {'pyppeteer': 'pyppeteer'}

readme_file = path.join(basedir, 'README.md')
with open(readme_file) as f:
    src = f.read()

try:
    from m2r import M2R
    readme = M2R()(src)
except ImportError:
    readme = src

requirements = [
    'pyee',
    'websockets',
]

test_requirements = [
    'syncer',
    'tornado>=5',
    'wdom',
]

setup(
    name='pyppeteer',
    version='0.0.13',
    description=('Headless chrome/chromium automation library '
                 '(unofficial port of puppeteer)'),
    long_description=readme,

    author="Hiroyuki Takagi",
    author_email='miyako.dev@gmail.com',
    url='https://github.com/miyakogi/pyppeteer',

    packages=packages,
    package_dir=package_dir,
    include_package_data=True,
    install_requires=requirements,

    license="MIT license",
    zip_safe=False,
    keywords='pyppeteer',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.5',
    test_suite='tests',
    tests_require=test_requirements,
    **extra_args,
)
