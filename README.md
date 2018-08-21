Pyppeteer
=========

[![PyPI](https://img.shields.io/pypi/v/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![PyPI version](https://img.shields.io/pypi/pyversions/pyppeteer.svg)](https://pypi.python.org/pypi/pyppeteer)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://miyakogi.github.io/pyppeteer)
[![Travis status](https://travis-ci.org/miyakogi/pyppeteer.svg)](https://travis-ci.org/miyakogi/pyppeteer)
[![AppVeyor status](https://ci.appveyor.com/api/projects/status/nb53tkg9po8v1blk?svg=true)](https://ci.appveyor.com/project/miyakogi/pyppeteer)
[![codecov](https://codecov.io/gh/miyakogi/pyppeteer/branch/master/graph/badge.svg)](https://codecov.io/gh/miyakogi/pyppeteer)

Unofficial Python port of
[puppeteer](https://github.com/GoogleChrome/puppeteer) JavaScript (headless)
chrome/chromium browser automation library.

* Free software: MIT license (including the work distributed under the Apache 2.0 license)
* Documentation: https://miyakogi.github.io/pyppeteer

## Installation

Pyppeteer requires python 3.6+.
(experimentally supports python 3.5)

Install by pip from PyPI:

```
python3 -m pip install pyppeteer
```

Or install latest version from [github](https://github.com/miyakogi/pyppeteer):

```
python3 -m pip install -U git+https://github.com/miyakogi/pyppeteer.git@dev
```

## Usage

> **Note**: When you run pyppeteer first time, it downloads a recent version of Chromium (~100MB).
> If you don't prefer this behavior, run `pyppeteer-install` command before running scripts which uses pyppeteer.

**Example**: open web page and take a screenshot.

```py
import asyncio
from pyppeteer import launch

async def main():
    browser = await launch()
    page = await browser.newPage()
    await page.goto('http://example.com')
    await page.screenshot({'path': 'example.png'})
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
```

**Example**: evaluate script on the page.

```py
import asyncio
from pyppeteer import launch

async def main():
    browser = await launch()
    page = await browser.newPage()
    await page.goto('http://example.com')
    await page.screenshot({'path': 'example.png'})

    dimensions = await page.evaluate('''() => {
        return {
            width: document.documentElement.clientWidth,
            height: document.documentElement.clientHeight,
            deviceScaleFactor: window.devicePixelRatio,
        }
    }''')

    print(dimensions)
    # >>> {'width': 800, 'height': 600, 'deviceScaleFactor': 1}
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
```

Pyppeteer has almost same API as puppeteer.
More APIs are listed in the
[document](https://miyakogi.github.io/pyppeteer/reference.html).

[Puppeteer's document](https://github.com/GoogleChrome/puppeteer/blob/master/docs/api.md#)
and [troubleshooting](https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md) are also useful for pyppeteer users.

## Differences between puppeteer and pyppeteer

Pyppeteer is to be as similar as puppeteer, but some differences between python
and JavaScript make it difficult.

These are differences between puppeteer and pyppeteer.

### Keyword arguments for options

Puppeteer uses object (dictionary in python) for passing options to
functions/methods. Pyppeteer accepts both dictionary and keyword arguments for
options.

Dictionary style option (similar to puppeteer):

```python
browser = await launch({'headless': True})
```

Keyword argument style option (more pythonic, isn't it?):

```python
browser = await launch(headless=True)
```

### Element selector method name (`$` -> `querySelector`)

In python, `$` is not usable for method name.
So pyppeteer uses
`Page.querySelector()`/`Page.querySelectorAll()`/`Page.xpath()` instead of
`Page.$()`/`Page.$$()`/`Page.$x()`. Pyppeteer also has shorthands for these
methods, `Page.J()`, `Page.JJ()`, and `Page.Jx()`.

### Arguments of `Page.evaluate()` and `Page.querySelectorEval()`

Puppeteer's version of `evaluate()` takes JavaScript raw function or string of
JavaScript expression, but pyppeteer takes string of JavaScript. JavaScript
strings can be function or expression. Pyppeteer tries to automatically detect
the string is function or expression, but sometimes it fails. If expression
string is treated as function and error is raised, add `force_expr=True` option,
which force pyppeteer to treat the string as expression.

Example to get page content:

```python
content = await page.evaluate('document.body.textContent', force_expr=True)
```

Example to get element's inner text:

```python
element = await page.querySelector('h1')
title = await page.evaluate('(element) => element.textContent', element)
```

## Future Plan

1. Catch up development of puppeteer
    * Not intend to add original API which puppeteer does not have

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage) project template.
