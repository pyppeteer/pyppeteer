pyppeteer
=========

[![PyPI](https://img.shields.io/pypi/v/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![PyPI version](https://img.shields.io/pypi/pyversions/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://miyakogi.github.io/pyppeteer)
[![Build Status](https://travis-ci.org/miyakogi/pyppeteer.svg?branch=master)](https://travis-ci.org/miyakogi/pyppeteer)
[![codecov](https://codecov.io/gh/miyakogi/pyppeteer/branch/master/graph/badge.svg)](https://codecov.io/ghmiyakogi//pyppeteer)

Unofficial Python port of [puppeteer](https://github.com/GoogleChrome/puppeteer)

# !!! WORK IN PROGRESS !!!

* Free software: MIT license (will be changed to Apache 2.0 license)
* Documentation: https://miyakogi.github.io/pyppeteer

## Installation

Pyppeteer requires python 3.6+.

```
pip install https://github.com/miyakogi/pyppeteer.git
```

## Usage

Below code open web page and take a screenshot.

```py
import asyncio
from pyppeteer.launcher import launch

async def main(browser):
    page = await browser.newPage()
    await page.goto('http://example.com')
    await page.screenshot({'path': 'example.png'})

browser = launch()
asyncio.get_event_loop().run_until_complete(main(browser))
browser.close()
```

Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
