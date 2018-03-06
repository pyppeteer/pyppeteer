History
=======

## Version 0.0.13 (next version)

* **`launch` is now coroutine** (breaking change)
* Implement `connect` function
* `PYPPETEER_DOWNLAOD_HOST` env variable specifies host part of URL to downlaod chromium
* Rename `setRequestInterceptionEnable` to `setRequestInterception`
* Implement `Browser.pages` to acccess all pages
    * Add `Target` class and some new method on Browser
* Refactor NavigatoinWatcher
    * add `documentloaded`, `networkidle0`, and `networkidle2` options
* `Request.abort` accepts error code.
* BugFix: Do not change original options dictionary

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
