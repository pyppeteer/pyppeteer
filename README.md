Pyppeteer
=========

[![PyPI](https://img.shields.io/pypi/v/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![PyPI version](https://img.shields.io/pypi/pyversions/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://miyakogi.github.io/pyppeteer)
[![Build Status](https://travis-ci.org/miyakogi/pyppeteer.svg?branch=master)](https://travis-ci.org/miyakogi/pyppeteer)
[![codecov](https://codecov.io/gh/miyakogi/pyppeteer/branch/master/graph/badge.svg)](https://codecov.io/ghmiyakogi//pyppeteer)

Unofficial Python port of
[puppeteer](https://github.com/GoogleChrome/puppeteer) JavaScript (headless)
chrome/chromium browser automation library.

* Free software: MIT license (including the work distributed under the Apache 2.0 license)
* Documentation: https://miyakogi.github.io/pyppeteer

## WORK IN PROGRESS

Not all features are implemented or tested currently.

* The following features are not implemented yet.
    * PDF screenshot
    * `Page.waitForSelector()` and `Frame.waitForSelector()`
    * `Page.waitForFunction()` and `Frame.waitForFunction()`

## Installation

Pyppeteer requires python 3.6+.

Install by pip from PyPI:

```
pytyon3 -m pip install pyppeteer
```

Or install latest version from github:

```
python3 -m pip install -U git+https://github.com/miyakogi/pyppeteer.git
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

Pyppeteer has almost same API as puppeteer.
More APIs are listed in the
[document](https://miyakogi.github.io/pyppeteer/reference.html).

[Puppeteer's document](https://github.com/GoogleChrome/puppeteer/blob/master/docs/api.md#)
is also useful for pyppeteer users.

### Differences between puppeteer and pyppeteer

Pyppeteer is to be as similar as puppeteer, but some differences between python
and JavaScript make it difficult.

These are differences between puppeteer and pyppeteer.

#### Element selector method name (`$` -> `querySelector`)

In python, `$` is not usable for method name.
So pyppeteer uses `Page.querySelector()` instead of `Page.$()`, and
`ElementHandle.querySelector()` instead of `ElementHandle.$()`.
Pyppeteer has shorthand of this method, `Page.J()` and `ElementHandle.J()`.

#### Argument of `Page.evaluate()` / `ElementHandle.evaluate()`

Puppeteer's version of `evaluate()` takes JavaScript raw function, but
pyppeteer takes string of JavaScript function.

Example to get element's inner text:

```python
element = page.querySelector('h1')
title = element.evaluate('(element) => element.textContent')
```

Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
