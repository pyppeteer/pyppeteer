API Reference
=============

Commands
--------

* ``pyppeteer-install``: Download and install chromium for pyppeteer.

Environment Variables
---------------------

* ``$PYPPETEER_HOME``: Specify the directory to be used by pyppeteer.
  Pyppeteer uses this directory for extracting downloaded Chromium, and for
  making temporary user data directory.
  Default location depends on platform:
  * Windows: `C:\Users\<username>\AppData\Local\pyppeteer`
  * OS X: `/Users/<username>/Library/Application Support/pyppeteer`
  * Linux: `/home/<username>/.local/share/pyppeteer`
    * or in `$XDG_DATA_HOME/pyppeteer` if `$XDG_DATA_HOME` is defined.

  Details see [appdirs](https://pypi.org/project/appdirs/)'s `user_data_dir`.

* ``$PYPPETEER_DOWNLOAD_HOST``: Overwrite host part of URL that is used to
  download Chromium. Defaults to ``https://storage.googleapis.com``.

* ``$PYPPETEER_CHROMIUM_REVISION``: Specify a certain version of chromium you'd
  like pyppeteer to use. Default value can be checked by
  ``pyppeteer.__chromium_revision__``.

* ``$PYPPETEER_NO_PROGRESS_BAR``: Suppress showing progress bar in chromium
  download process. Acceptable values are ``1`` or ``true`` (case-insensitive).


Pyppeteer Main Module
---------------------

.. currentmodule:: pyppeteer

.. autofunction:: launch
.. autofunction:: connect
.. autofunction:: defaultArgs
.. autofunction:: executablePath

Browser Class
-------------

.. currentmodule:: pyppeteer.browser

.. autoclass:: pyppeteer.browser.Browser
   :members:
   :exclude-members: create

BrowserContext Class
--------------------

.. currentmodule:: pyppeteer.browser

.. autoclass:: pyppeteer.browser.BrowserContext
   :members:

Page Class
----------

.. currentmodule:: pyppeteer.page

.. autoclass:: pyppeteer.page.Page
   :members:
   :exclude-members: create

Worker Class
------------

.. currentmodule:: pyppeteer.worker

.. autoclass:: pyppeteer.worker.Worker
   :members:

Keyboard Class
--------------

.. currentmodule:: pyppeteer.input

.. autoclass:: pyppeteer.input.Keyboard
   :members:

Mouse Class
-----------

.. currentmodule:: pyppeteer.input

.. autoclass:: pyppeteer.input.Mouse
   :members:

Tracing Class
-------------

.. currentmodule:: pyppeteer.tracing

.. autoclass:: pyppeteer.tracing.Tracing
   :members:

Dialog Class
------------

.. currentmodule:: pyppeteer.dialog

.. autoclass:: pyppeteer.dialog.Dialog
   :members:

ConsoleMessage Class
--------------------

.. currentmodule:: pyppeteer.page

.. autoclass:: pyppeteer.page.ConsoleMessage
   :members:

Frame Class
-----------

.. currentmodule:: pyppeteer.frame

.. autoclass:: pyppeteer.frame_manager.Frame
   :members:

ExecutionContext Class
----------------------

.. currentmodule:: pyppeteer.execution_context

.. autoclass:: pyppeteer.execution_context.ExecutionContext
   :members:

JSHandle Class
--------------

.. autoclass:: pyppeteer.execution_context.JSHandle
   :members:

ElementHandle Class
-------------------

.. currentmodule:: pyppeteer.element_handle

.. autoclass:: pyppeteer.element_handle.ElementHandle
   :members:

Request Class
-------------

.. currentmodule:: pyppeteer.network_manager

.. autoclass:: pyppeteer.network_manager.Request
   :members:

Response Class
--------------

.. currentmodule:: pyppeteer.network_manager

.. autoclass:: pyppeteer.network_manager.Response
   :members:

Target Class
------------

.. currentmodule:: pyppeteer.target

.. autoclass:: pyppeteer.target.Target
   :members:

CDPSession Class
----------------

.. currentmodule:: pyppeteer.connection

.. autoclass:: pyppeteer.connection.CDPSession
   :members:

Coverage Class
--------------

.. currentmodule:: pyppeteer.coverage

.. autoclass:: pyppeteer.coverage.Coverage
   :members:

Debugging
---------

For debugging, you can set `logLevel` option to `logging.DEBUG` for
:func:`pyppeteer.launcher.launch` and :func:`pyppeteer.launcher.connect`
functions. However, this option prints too many logs including SEND/RECV
messages of pyppeteer. In order to only show suppressed error messages, you
should set ``pyppeteer.DEBUG`` to ``True``.

Example:

```python
import asyncio
import pyppeteer
from pyppeteer import launch

pyppeteer.DEBUG = True  # print suppressed errors as error log

async def main():
    browser = await launch()
    ...  # do something

asyncio.get_event_loop().run_until_complete(main())
```
