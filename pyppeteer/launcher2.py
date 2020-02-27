import asyncio
import atexit
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from signal import signal, SIGTERM, SIGINT, SIGKILL, SIG_DFL
from typing import Dict, Sequence, Union, TypedDict, List, Optional, Awaitable
from urllib.error import URLError
from urllib.request import urlopen

import websockets

from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.helper import debugError, logger
from pyppeteer.util import merge_dict

if sys.platform.startswith('win'):
    from signal import SIGHUP

logger = logging.getLogger(__name__)


class ChromeArgOptions(TypedDict):
    headless: bool
    args: List[str]
    userDataDir: str
    devtools: bool


class LaunchOptions(TypedDict):
    executablePath: str
    ignoreDefaultArgs: Union[False, List[str]]
    handleSIGINT: bool
    handleSIGTERM: bool
    handleSIGSIGHUP: bool
    timeout: float
    dumpio: bool
    env: Dict[str, Union[str, bool]]


class Viewport(TypedDict):
    width: float
    height: float
    deviceScaleFactor: Optional[float]
    isMobile: Optional[bool]
    isLandscape: Optional[bool]
    hasTouch: Optional[bool]


class BrowserOptions(TypedDict):
    ignoreHTTPSErrors: Optional[bool]
    defaultViewport: Optional[Viewport]
    slowMo: Optional[bool]


class BrowserRunner:
    # todo: proper typing
    def __init__(self, executable_path: str, process_args: Sequence[str], temp_dir: Union[Path, str]):
        self.executable_path = executable_path
        self.process_args = process_args or []
        self.temp_dir = Path(temp_dir) if isinstance(temp_dir, str) else temp_dir

        self.proc = None
        self.connection = None

        self._closed = True
        self._listeners = []

    def start(self, options: LaunchOptions, **kwargs: LaunchOptions):
        options = merge_dict(options, kwargs)

        process_opts = {}
        if options.get('pipe'):
            raise NotImplementedError('Communication via pipe not supported')
        if options.get('env'):
            process_opts['env'] = options.get('env')
        # todo: dumpio
        if not options.get('dumpio'):
            process_opts['stdout'] = subprocess.PIPE
            process_opts['stderr'] = subprocess.STDOUT

        assert self.proc is None, 'This process has previously been started'

        self.proc = subprocess.Popen([self.executable_path, *self.process_args], **process_opts)
        self._closed = False

        def _close_proc(_, __):
            if not self._closed:
                # todo: implement cleaning up temp_dir
                pass

        if options.get('autoClose'):
            atexit.register(_close_proc)
        if options.get('handleSIGINT'):
            signal(SIGINT, _close_proc)
        if options.get('handleSIGTERM'):
            signal(SIGTERM, _close_proc)
        # SIGHUP is not defined on windows
        if not sys.platform.startswith('win'):
            if options.get('handleSIGINT'):
                signal(SIGHUP, _close_proc)

    def _restore_default_signal_handlers(self):
        signal(SIGKILL, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        if not sys.platform.startswith('win'):
            signal(SIGHUP, SIG_DFL)

    async def close(self) -> None:
        if not self._closed:
            if self.temp_dir:
                self.kill()
            elif self.connection:
                try:
                    await self.connection.send('Browser.close')
                except Exception as e:
                    debugError(logger, e)
                    self.kill()

    def kill(self) -> None:
        if self.proc and not self._closed and self.proc.returncode is not None:
            self.proc.kill()
        try:
            # todo: implement cleaning up temp_dir
            pass
        except Exception:
            pass

    async def setupConnection(self, usePipe: bool, timeout: float, slowMo: float, preferredRevision: str,
                              loop) -> Awaitable:
        if usePipe:
            raise NotImplementedError('Communication via pipe not supported')
        loop = loop or asyncio.get_event_loop()
        delay = slowMo or 0
        wsEndpointUrl = getWSEndpoint(options.get)  # todo: url
        ws_endpoint = websockets.client.connect(
            self._url, max_size=None, loop=self._loop, ping_interval=None, ping_timeout=None)
        self.connection = Connection(ws_endpoint, loop, delay)


def getWSEndpoint(url) -> str:
    url += '/json/version'
    timeout = time.perf_counter() + 30
    while True:
        if time.perf_counter() > timeout:
            raise BrowserError('Browser closed unexpectedly:\n')
        try:
            with urlopen(url) as f:
                data = json.loads(f.read().decode())
            break
        except URLError:
            time.sleep(0.1)

    return data['webSocketDebuggerUrl']


def launcher(projectRoot: str = None, prefferedRevision: str = None, product: str = None):
    """Returns the appropriate browser launcher class instance"""
    env = os.environ
    PRODUCT_ENV_VARS = [
        'PUPPETEER_PRODUCT',
        'npm_config_puppeteer_product',
        'npm_package_config_puppeteer_product',
        'PYPPETEER_PRODUCT'
    ]
    product_env_vars_val = [env.get(x) for x in PRODUCT_ENV_VARS]
    product = next(x for x in [product] + product_env_vars_val if x)
    if product == 'firefox':
        return FirefoxLauncher(projectRoot, prefferedRevision)
    else:
        return ChromeLauncher(projectRoot, prefferedRevision)
