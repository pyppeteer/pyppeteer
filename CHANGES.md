History
=======

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
* Add `SecurityDetauls` class and `response.secutiryDetails`
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

* BugFIx: Skip SIGHUP option on windows (windows does not support this signal)


## Version 0.0.15 (2018-03-22)

Catch up puppeteer v1.0.0

* Support `raf` and `mutation` polling for `waitFor*` methods
* Add `Page.coverage` to support JS and CSS coverage
* Add XPath support with `Page.xpath`, `Frame.xpath`, and `ElementHandle.xpath`
* Add `Target.createCDPSession` to work with raw Devtools Protocol
* Change `Frame.executionContest` from property to coroutine
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
* `PYPPETEER_DOWNLAOD_HOST` env variable specifies host part of URL to downlaod chromium
* Rename `setRequestInterceptionEnable` to `setRequestInterception`
* Rename `Page.getMetrics` to `Page.metrics`
* Implement `Browser.pages` to acccess all pages
    * Add `Target` class and some new method on Browser
* Add `ElementHandle.querySelector` and `ElementHandle.querySelectorAll`
* Refactor NavigatoinWatcher
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
    * Console api
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
* Add `ElementHandle.boudingBox` and `ElementHandle.screenshot`
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
