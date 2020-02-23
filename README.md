pyppeteer2
==========

[![PyPI](https://img.shields.io/pypi/v/pyppeteer2.svg)](https://pypi.python.org/pypi/pyppeteer2)
[![PyPI version](https://img.shields.io/pypi/pyversions/pyppeteer2.svg)](https://pypi.python.org/pypi/pyppeteer2)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://miyakogi.github.io/pyppeteer2)
[![Travis status](https://travis-ci.org/miyakogi/pyppeteer2.svg)](https://travis-ci.org/miyakogi/pyppeteer2)
[![AppVeyor status](https://ci.appveyor.com/api/projects/status/nb53tkg9po8v1blk?svg=true)](https://ci.appveyor.com/project/miyakogi/pyppeteer2)
[![codecov](https://codecov.io/gh/miyakogi/pyppeteer2/branch/master/graph/badge.svg)](https://codecov.io/gh/miyakogi/pyppeteer2)

_Note: this is a WIP continuation of pyppeteer project_  

Unofficial Python port of
[puppeteer](https://github.com/GoogleChrome/puppeteer) JavaScript (headless) chrome/chromium browser automation library.

* Free software: MIT license (including the work distributed under the Apache 2.0 license)
* Documentation: https://miyakogi.github.io/pyppeteer

## Installation

pyppeteer2 requires Python >= 3.6

Install with `pip` from PyPI:

```
pip install pyppeteer
```

Or install latest version from [github](https://github.com/pyppeteer/pyppeteer2/):

```
pip install -U git+https://github.com/pyppeteer/pyppeteer2@dev
```

## Usage

> **Note**: When you run pyppeteer2 first time, it downloads a recent version of Chromium (~100MB) if it is not available.
> If you don't prefer this behavior, ensure that a suitable Chrome binary is installed. One way to do this is to run `pyppeteer-install` command before prior to using this library.

### Examples
Open web page and take a screenshot.
```py
import asyncio
from pyppeteer import launch

async def main():
    browser = await launch()
    page = await browser.newPage()
    await page.goto('https://example.com')
    await page.screenshot({'path': 'example.png'})
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
```

Evaluate javascript on a page.

```py
import asyncio
from pyppeteer import launch

async def main():
    browser = await launch()
    page = await browser.newPage()
    await page.goto('https://example.com')
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

pyppeteer2 has almost same API as puppeteer.
More APIs are listed in the
[document](https://miyakogi.github.io/pyppeteer/reference.html).

[Puppeteer's document](https://github.com/GoogleChrome/puppeteer/blob/master/docs/api.md#)
and [troubleshooting](https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md) are also useful for pyppeteer users.

## Differences between puppeteer and pyppeteer2

pyppeteer2 strives to replicate the puppeteer API as close as possible, however, fundamental differences between Javascript and Python make this difficult to do exactly.

### Keyword arguments for options

Puppeteer uses object (dictionary in python) for passing options to
functions/methods. pyppeteer2 accepts both dictionary and keyword arguments for
options.

Dictionary style option (similar to puppeteer):

```python
browser = await launch({'headless': True})
```

Keyword argument style option (more pythonic, isn't it?):

```python
browser = await launch(headless=True)
```

### Element selector method names

In python, `$` is not a valid identifier. The equivalent methods to Puppeteer's `$`, `$$`, and `$x` and shorthand methods are listed below:

| puppeteer | pyppeteer2               | pyppeteer2 shorthand |
|-----------|-------------------------|---------------------|
| Page.$()  | Page.querySelector()    | Page.J()            |
| Page.$$() | Page.querySelectorAll() | Page.JJ()           |
| Page.$x() | Page.xpath()            | Page.Jx()           |

### Arguments of `Page.evaluate()` and `Page.querySelectorEval()`

Puppeteer's version of `evaluate()` takes a JavaScript function or a string representation of a JavaScript expression. pyppeteer2 takes string representation of JavaScript expression or function. pyppeteer2 will try to automatically detect if the string is function or expression, but it will fail sometimes. If an expression
string is erroneously treated as function and an error is raised, set `force_expr` to `True`,
to force pyppeteer2 to treat the string as expression.

### Examples:

Get a page's `textContent`:

```python
content = await page.evaluate('document.body.textContent', force_expr=True)
```

Get an element's `textContent`:

```python
element = await page.querySelector('h1')
title = await page.evaluate('(element) => element.textContent', element)
```

## Roadmap

See [projects](https://github.com/pyppeteer/pyppeteer2/projects)

## Credits

###### This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage) project template.
