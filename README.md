Pyppeteer
=========

[![PyPI](https://img.shields.io/pypi/v/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![PyPI version](https://img.shields.io/pypi/pyversions/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://miyakogi.github.io/pyppeteer)
[![Build Status](https://travis-ci.org/miyakogi/pyppeteer.svg?branch=master)](https://travis-ci.org/miyakogi/pyppeteer)
[![codecov](https://codecov.io/gh/miyakogi/pyppeteer/branch/master/graph/badge.svg)](https://codecov.io/gh/miyakogi/pyppeteer)

Unofficial Python port of
[puppeteer](https://github.com/GoogleChrome/puppeteer) JavaScript (headless)
chrome/chromium browser automation library.

* Free software: MIT license (including the work distributed under the Apache 2.0 license)
* Documentation: https://miyakogi.github.io/pyppeteer

## WORK IN PROGRESS

Currently not all features are tested.

## Installation

Pyppeteer requires python 3.6+.
(experimentally supports python 3.5)

Install by pip from PyPI:

```
python3 -m pip install pyppeteer
```

Or install latest version from github:

```
python3 -m pip install -U git+https://github.com/miyakogi/pyppeteer.git@dev
```

## Usage

Below code open web page and take a screenshot.

```py
import asyncio
from pyppeteer.launcher import launch

async def main():
    page = await browser.newPage()
    await page.goto('http://example.com')
    await page.screenshot({'path': 'example.png'})

browser = launch()
asyncio.get_event_loop().run_until_complete(main())
browser.close()
```

Pyppeteer has almost same API as puppeteer.
More APIs are listed in the
[document](https://miyakogi.github.io/pyppeteer/reference.html).

[Puppeteer's document](https://github.com/GoogleChrome/puppeteer/blob/master/docs/api.md#)
is also useful for pyppeteer users.

## Differences between puppeteer and pyppeteer

Pyppeteer is to be as similar as puppeteer, but some differences between python
and JavaScript make it difficult.

These are differences between puppeteer and pyppeteer.

### Keyword argument for options

Puppeteer uses object (dictionary in python) for passing options to functions/methods.
Pyppeteer accepts both dictionary and keyword argument for options.

Dictionary style option (similar to puppeteer):

```python
browser = launch({'headless': True})
```

Keyword argument style option (more pythonic, isn't it?):

```python
browser = launch(headless=True)
```

### Element selector method name (`$` -> `querySelector`)

In python, `$` is not usable for method name.
So pyppeteer uses `Page.querySelector()` instead of `Page.$()`, and
`ElementHandle.querySelector()` instead of `ElementHandle.$()`.
Pyppeteer has shorthand of this method, `Page.J()` and `ElementHandle.J()`.

### Argument of `Page.evaluate()` / `ElementHandle.evaluate()`

Puppeteer's version of `evaluate()` takes JavaScript raw function, but
pyppeteer takes string of JavaScript function.

Example to get element's inner text:

```python
element = await page.querySelector('h1')
title = await element.evaluate('(element) => element.textContent')
```

Credits
---------

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage) project template.
