History
=======

## Version ?.?.? (next version, pup2.1.1 overhaul)

* [populate me]

## Version 0.2.5

* Match package version and \_\_version__ (🤦‍♂️)
* Use `importlib_metadata` so this isn't a problem in the future

## Version 0.2.4

* Update `pyee` dependency breaking build failures on NixOS + Fedora packaging systems (#207)

## Version 0.2.3

* Hotfix: random freezes from sending stdout to PIPE instead of DEVNULL
* Fix `tests` package being installed for no reason

## Version 0.0.26

* Add `$PYPPETEER_NO_PROGRESS_BAR` environment variable
* `pyppeteer.defaultArgs` now accepts that help infer chromium command-line flags.
* `pyppeteer.launch()` argument `ignoreDefaultArgs` now accepts a list of flags to ignore.
* `Page.type()` now supports typing emoji
* `Page.pdf()` accepts a new argument `preferCSSPageSize`
* Add new option `defaultViewport` to `launch()` and `connect()`
* Add `BrowserContext.pages()` method

## Version 0.0.25 (2018-09-27)

* Fix miss-spelled methods and functions
  * Change `Browser.isIncognite` to `Browser.isIncognito`
  * Change `Browser.createIncogniteBrowserContext` to `Browser.createIncognitoBrowserContext`
  * Change `chromium_excutable` to `chromium_executable`
  * Remove `craete` function in `page.py`

## Version 0.0.24 (2018-09-12)

Catch up puppeteer v1.6.0

* Add `ElementHandle.isIntersectingViewport()`
* Add `reportAnonymousScript` option to `Coverage.startJSCoverage()`
* Add `Page.waitForRequest` and `Page.waitForResponse` methods
* Now possible to attach to extension background pages with `Target.page()`
* Improved reliability of clicking with `Page.click()` and `ElementHandle.click()`

## Version 0.0.23 (2018-09-10)

Catch up puppeteer v1.5.0

* Add `BrowserContext` class
* Add `Worker` class
* Change `CDPSession.send` to a normal function which returns awaitable value
* Add `Page.isClosed` method
* Add `ElementHandle.querySelectorAllEval` and `ElementHandle.JJeval`
* Add `Target.opener`
* Add `Request.isNavigationRequest`

## Version 0.0.22 (2018-09-06)

Catch up puppeteer v1.4.0

* Add `pyppeteer.DEBUG` variable
* Add `Page.browser`
* Add `Target.browser`
* Add `ElementHandle.querySelectorEval` and `ElementHandle.Jeval`
* Add `runBeforeUnload` option to `Page.close` method
* Change `Page.querySelectorEval` to raise `ElementHandleError` when element which matches `selector` is not found
* Report 'Log' domain entries as 'console' events
* Fix `Page.goto` to return response when page pushes new state
* (OS X) Suppress long log when extracting chromium


## Version 0.0.21 (2018-08-21)

Catch up puppeteer v1.3.0

* Add `pyppeteer-install` command
* Add `autoClose` option to `launch` function
* Add `loop` option to `launch` function (experimental)
* Add `Page.setBypassCSP` method
* `Page.tracing.stop` returns result data
* Rename `documentloaded` to `domcontentloaded` on `waitUntil` option
* Fix `slowMo` option
* Fix anchor navigation
* Fix to return response via redirects
* Continue to find WS URL while process is alive


## Version 0.0.20 (2018-08-11)

* Run on msys/cygwin, anyway
* Raise error correctly when connection failed (PR#91)
* Change browser download location and temporary user data directory to:
    * If `$PYPPETEER_HOME` environment variable is defined, use this location
    * Otherwise, use platform dependent locations, based on [appdirs](https://pypi.org/project/appdirs/):
        * `'C:\Users\<username>\AppData\Local\pyppeteer'` (Windows)
        * `'/Users/<username>/Library/Application Support/pyppeteer'` (OS X)
        * `'/home/<username>/.local/share/pyppeteer'` (Linux)
            * or in `'$XDG_DATA_HOME/pyppeteer'` if `$XDG_DATA_HOME` is defined

* Introduce `$PYPPETEER_CHROMIUM_REVISION`
* Introduce `$PYPPETEER_HOME`
* Add `logLevel` option to `launch` and `connect` functions
* Add page `close` event
* Add `ElementHandle.boxModel` method
* Add an option to disable timeout for `waitFor` functions


## Version 0.0.19 (2018-07-05)

Catch up puppeteer v1.2.0

* Add `ElementHandle.contentFrame` method
* Add `Request.redirectChain` method
* `Page.addScriptTag` accepts a new option `type`


## Version 0.0.18 (2018-07-04)

Catch up puppeteer v1.1.1

* Add `Page.waitForXPath` and `Frame.waitForXPath`
* `Page.waitFor` accepts xpath string which starts with `//`
* Add `Response.fromCache` and `Response.fromServiceWorker`
* Add `SecurityDetails` class and `response.securityDetails`
* Add `Page.setCacheEnabled` method
* Add `ExecutionContext.frame`
* Add `dumpio` option to `launch` function
* Add `slowMo` option to `connect` function
* `launcher.connect` can be access from package top
  * `from pyppeteer import connect` is now valid
* Add `Frame.evaluateHandle`
* Add `Page.Events.DOMContentLoaded`


## Version 0.0.17 (2018-04-02)

* Mark as alpha

* Gracefully terminate browser process
* `Request.method` and `Request.postData` return `None` if no data
* Change `Target.url` and `Target.type` to properties
* Change `Dialog.message` and `Dialog.defaultValue` to properties
* Fix: properly emit `Browser.targetChanged` events
* Fix: properly emit `Browser.targetDestroyed` events


## Version 0.0.16 (2018-03-23)

* BugFix: Skip SIGHUP option on windows (windows does not support this signal)


## Version 0.0.15 (2018-03-22)

Catch up puppeteer v1.0.0

* Support `raf` and `mutation` polling for `waitFor*` methods
* Add `Page.coverage` to support JS and CSS coverage
* Add XPath support with `Page.xpath`, `Frame.xpath`, and `ElementHandle.xpath`
* Add `Target.createCDPSession` to work with raw Devtools Protocol
* Change `Frame.executionContext` from property to coroutine
* Add `ignoreDefaultArgs` option to `pyppeteer.launch`
* Add `handleSIGINT`/`handleSIGTERM`/`handleSIGHUP` options to `pyppeteer.launch`
* Add `Page.setDefaultNavigationTimeout` method
* `Page.waitFor*` methods accept `JSHandle` as argument
* Implement `Frame.content` and `Frame.setContent` methods
* `page.tracing.start` accepts custom tracing categories option
* Add `Browser.process` property
* Add `Request.frame` property


## Version 0.0.14 (2018-03-14)

* Read WS endpoint from web interface instead of stdout
* Pass environment variables of python process to chrome by default
* Do not limit size of websocket frames

* BugFix:
    * `Keyboard.type`
    * `Page.Events.Metrics`

## Version 0.0.13 (2018-03-10)

Catch up puppeteer v0.13.0

* `pyppeteer.launch()` is now **coroutine**
* Implement `connect` function
* `PYPPETEER_DOWNLOAD_HOST` env variable specifies host part of URL to download chromium
* Rename `setRequestInterceptionEnable` to `setRequestInterception`
* Rename `Page.getMetrics` to `Page.metrics`
* Implement `Browser.pages` to access all pages
    * Add `Target` class and some new method on Browser
* Add `ElementHandle.querySelector` and `ElementHandle.querySelectorAll`
* Refactor NavigatorWatcher
    * add `documentloaded`, `networkidle0`, and `networkidle2` options
* `Request.abort` accepts error code
* `addScriptTag` and `addStyleTag` return `ElementHandle`
* Add `force_expr` option to `evaluate` method
* `Page.select` returns selected values
* Add `pyppeteer.version` and `pyppeteer.version_info`

* BugFix:
    * Do not change original options dictionary
    * `Page.frames`
    * `Page.queryObjects`
    * `Page.exposeFunction`
    * Request interception
    * Console API
    * websocket error on closing browser (#24)

## Version 0.0.12 (2018-03-01)

* BugFix (#33)

## Version 0.0.11 (2018-03-01)

Catch up puppeteer v0.12.0

* Remove `ElementHandle.evaluate`
* Remove `ElementHandle.attribute`
* Deprecate `Page.plainText`
* Deprecate `Page.injectFile`
* Add `Page.querySelectorAllEval`
* Add `Page.select` and `Page.type`
* Add `ElementHandle.boundingBox` and `ElementHandle.screenshot`
* Add `ElementHandle.focus`, `ElementHandle.type`, and `ElementHandle.press`
* Add `getMetrics` method
* Add `offlineMode`

## Version 0.0.10 (2018-02-27)

* Enable to import `launch` from package root
* Change `browser.close` to coroutine function
* Catch up puppeteer v0.11.0

### Version 0.0.9 (2017-09-09)

* Delete temporary user data directory when browser closed
* Fix bug to fail extracting zip on mac

### Version 0.0.8 (2017-09-03)

* Change chromium revision
* Support steps option of `Mouse.move()`
* Experimentally supports python 3.5 by py-backwards

### Version 0.0.7 (2017-09-03)

* Catch up puppeteer v0.10.2
    * Add `Page.querySelectorEval` (`Page.$eval` in puppeteer)
    * Deprecate `ElementHandle.attribute`
    * Add `Touchscreen` class and implement `Page.tap` and `ElementHandle.tap`

### Version 0.0.6 (2017-09-02)

* Accept keyword arguments for options
* Faster polling on `waitFor*` functions
* Fix bugs

### Version 0.0.5 (2017-08-30)

* Implement pdf printing
* Implement `waitFor*` functions

### Version 0.0.4 (2017-08-30)

* Register PyPI
