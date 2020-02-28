import asyncio
import atexit
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from signal import signal, SIGTERM, SIGINT, SIGKILL, SIG_DFL
from typing import Dict, Sequence, Union, TypedDict, List, Optional, Awaitable, Any
from urllib.error import URLError
from urllib.request import urlopen

import websockets

from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.helper import debugError, logger
from pyppeteer.util import merge_dict, get_free_port

if sys.platform.startswith('win'):
    from signal import SIGHUP

logger = logging.getLogger(__name__)


class ChromeArgOptions(TypedDict):
    headless: Optional[bool]
    args: List[str]
    userDataDir: Optional[str]
    devtools: Optional[bool]


class LaunchOptions(TypedDict):
    executablePath: str
    ignoreDefaultArgs: Union[False, List[str]]
    handleSIGINT: bool
    handleSIGTERM: bool
    handleSIGHUP: bool
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

    def start(self, **kwargs: LaunchOptions):
        process_opts = {}
        if kwargs.get('pipe'):
            raise NotImplementedError('Communication via pipe not supported')
        if kwargs.get('env'):
            process_opts['env'] = kwargs.get('env')
        # todo: dumpio
        if not kwargs.get('dumpio'):
            process_opts['stdout'] = subprocess.PIPE
            process_opts['stderr'] = subprocess.STDOUT

        assert self.proc is None, 'This process has previously been started'

        self.proc = subprocess.Popen([self.executable_path, *self.process_args], **process_opts)
        self._closed = False

        def _close_proc(_, __):
            if not self._closed:
                # todo: implement cleaning up temp_dir
                pass

        if kwargs.get('autoClose'):
            atexit.register(_close_proc)
        if kwargs.get('handleSIGINT'):
            signal(SIGINT, _close_proc)
        if kwargs.get('handleSIGTERM'):
            signal(SIGTERM, _close_proc)
        # SIGHUP is not defined on windows
        if not sys.platform.startswith('win'):
            if kwargs.get('handleSIGINT'):
                signal(SIGHUP, _close_proc)

    def _restore_default_signal_handlers(self):
        signal(SIGKILL, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        if not sys.platform.startswith('win'):
            signal(SIGHUP, SIG_DFL)

    async def close(self) -> Awaitable[None]:
        if not self._closed:
            self._restore_default_signal_handlers()
            if self.temp_dir:
                self.kill()
            elif self.connection:
                try:
                    return await self.connection.send('Browser.close')
                except Exception as e:
                    debugError(logger, e)
                    self.kill()

    def kill(self) -> None:
        if self.proc and not self._closed and self.proc.returncode is not None:
            self._restore_default_signal_handlers()
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
        wsEndpointUrl = getWSEndpoint(None)  # todo: url
        ws_endpoint = websockets.client.connect(self._url, max_size=None, loop=self._loop, ping_interval=None,
                                                ping_timeout=None)
        self.connection = Connection(ws_endpoint, loop, delay)


class ChromeLauncher:
    DEFAULT_ARGS = [
        '--disable-background-networking',
        '--enable-features=NetworkService,NetworkServiceInProcess',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-breakpad',
        '--disable-client-side-phishing-detection',
        '--disable-component-extensions-with-background-pages',
        '--disable-default-apps',
        '--disable-dev-shm-usage',
        '--disable-extensions',
        '--disable-features=TranslateUI',
        '--disable-hang-monitor',
        '--disable-ipc-flooding-protection',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-renderer-backgrounding',
        '--disable-sync',
        '--force-color-profile=srgb',
        '--metrics-recording-only',
        '--no-first-run',
        '--enable-automation',
        '--password-store=basic',
        '--use-mock-keychain',
    ]
    product = 'chrome'

    def __init__(self, projectRoot: str, prefferedRevision: str):
        self.projectRoot = projectRoot
        self.preferredRevision = prefferedRevision

    async def launch(self, **kwargs: Union[LaunchOptions, ChromeArgOptions, BrowserOptions]):
        ignoreDefaultArgs = kwargs.get('ignoreDefaultArgs', False)
        args = kwargs.get('args', [])
        dumpio = kwargs.get('dumpio', False)
        executablePath = kwargs.get('executablePath', None)
        env = kwargs.get('env', os.environ)
        handleSIGINT = kwargs.get('handleSIGINT', True)
        handleSIGTERM = kwargs.get('handleSIGTERM', True)
        handleSIGHUP = kwargs.get('handleSIGHUP', True)
        ignoreHTTPSErrors = kwargs.get('ignoreHTTPSErrors', False)
        defaultViewport = kwargs.get('defaultViewport', {'width': 800, 'height': 600})
        slowMo = kwargs.get('slowMo', 0)
        timeout = kwargs.get('timeout', 30_000)


        chrome_args = []
        if not ignoreDefaultArgs:
            chrome_args.extend(self.default_args(kwargs))
        elif isinstance(ignoreDefaultArgs, list):
            chrome_args.extend([x for x in self.default_args(args) if x not in ignoreDefaultArgs])
        else:
            chrome_args.extend(args)

        if not any(x.startswith('--remote-debugging-') for x in chrome_args):
            chrome_args.append(f'--remote-debugging-port={get_free_port()}')
        if not any(x.startswith(f'--user-data-dir') for x in chrome_args):
            profile_path = tempfile.TemporaryDirectory(prefix='pyppeteer2_profile_')
            chrome_args.append(f'--user-data-dir={profile_path.name}')

        chrome_executable = executablePath
        if not chrome_executable:
            # todo: implement
            chrome_executable = resolveExecutablePath(None)
        runner = BrowserRunner(chrome_executable, chrome_args, profile_path)
        runner.start(handleSIGINT=handleSIGINT, handleSIGHUP=handleSIGHUP, handleSIGTERM=handleSIGTERM)

        try:
            con = await runner.setupConnection()
            browser = await Browser.create(
                connection=con, contextIds=[], ignoreHTTPSErrors=ignoreHTTPSErrors,
                defaultViewport=defaultViewport, process=runner.proc, closeCallback=runner.close
            )
            await browser.waitForTarget(lambda x: x.type() == 'page')
            return browser
        finally:
            try:
                runner.kill()
            except Exception:
                pass





    def default_args(self, launch_kwargs: Dict[str, Any]):
        chrome_args = self.DEFAULT_ARGS[:]
        devtools = launch_kwargs.get('devtools', False)
        headless = launch_kwargs.get('headless', not devtools)
        args = launch_kwargs.get('args', [])
        userDataDir = launch_kwargs.get('userDataDir')

        if userDataDir:
            chrome_args.append(f'--user-data-dir={userDataDir}')
        if devtools:
            chrome_args.append('--auto-open-devtools-for-tabs')
        if headless:
            chrome_args.extend(['--headless', '--hide-scrollbars', '--mute-audio'])
        if all(x.startswith('-') for x in args):
            chrome_args.append('about:blank')
        chrome_args.extend(args)
        return chrome_args


class FirefoxLauncher:
    def __init__(self):
        raise NotImplementedError()

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


def waitForWSEndpoint():
    # todo: implement
    pass


def resolveExecutablePath(*_, **__):
    pass

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
