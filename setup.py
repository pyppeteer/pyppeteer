#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path
from setuptools import setup
import sys

basedir = path.dirname(path.abspath(__file__))
extra_args = {}

if (3, 6) > sys.version_info >= (3, 5):
    try:
        from py_backwards.compiler import compile_files
    except ImportError:
        import subprocess
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'py-backwards']
        )
        from py_backwards.compiler import compile_files
    in_dir = path.join(basedir, 'pyppeteer')
    out_dir = path.join(basedir, '.pyppeteer')
    compile_files(in_dir, out_dir, (3, 5))
    packages = ['pyppeteer']
    package_dir = {'pyppeteer': '.pyppeteer'}
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
    'tornado',
    'wdom',
]

setup(
    name='pyppeteer',
    version='0.0.7',
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
