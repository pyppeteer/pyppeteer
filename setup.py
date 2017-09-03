#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path
import sys

extra_args = {}
if (3, 6) > sys.version_info and sys.version_info >= (3, 5):
    try:
        from py_backwards_packager import setup
    except ImportError:
        import subprocess
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'py-backwards-packager']
        )
        from py_backwards_packager import setup
    extra_args['py_backwards_targets'] = ['3.5']
else:
    from setuptools import setup

basedir = path.dirname(path.abspath(__file__))
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

    packages=[
        'pyppeteer',
    ],
    package_dir={'pyppeteer': 'pyppeteer'},
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
