import atexit
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from signal import signal, SIGTERM, SIGINT, SIGKILL, SIG_DFL
from typing import Dict, Sequence, Union, TypedDict, List, Optional, Awaitable, Any, Tuple
from urllib.error import URLError
from urllib.request import urlopen

import websockets

from pyppeteer.browser import Browser
from pyppeteer.connection import Connection
from pyppeteer.errors import BrowserError
from pyppeteer.helper import debugError, logger
from pyppeteer.util import get_free_port

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
    def __init__(
            self,
            executable_path: str,
            process_args: Sequence[str],
            temp_dir: tempfile.TemporaryDirectory = None,
    ):
        self.executable_path = executable_path
        self.process_args = process_args or []
        self.temp_dir = temp_dir

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
        # todo: dumpio. See: https://pptr.dev/#?product=Puppeteer&version=v2.1.1&show=api-puppeteerlaunchoptions
        if not kwargs.get('dumpio'):
            process_opts['stdout'] = subprocess.PIPE
            process_opts['stderr'] = subprocess.STDOUT

        assert self.proc is None, 'This process has previously been started'

        self.proc = subprocess.Popen([self.executable_path, *self.process_args], **process_opts)
        self._closed = False

        async def _close_proc(_, __):
            if not self._closed:
                if self.connection and self.connection._connected:
                    await self.connection.send('Browser.close')
                    await self.connection.dispose()
                if self.temp_dir:
                    self._wait_for_proc_to_close()
                    self.temp_dir.cleanup()

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

    def _wait_for_proc_to_close(self):
        if self.proc.poll() is None and not self._closed:
            try:
                self.proc.terminator()
                self.proc.wait()
            except Exception:
                pass

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
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    async def setupConnection(
            self,
            usePipe: bool = None,
            timeout: float = None,
            slowMo: float = None,
            preferredRevision: str = None,
    ) -> Connection:

        if usePipe:
            raise NotImplementedError('Communication via pipe not supported')

        delay = slowMo or 0
        ws_endpoint_url = waitForWSEndpoint(self.proc, timeout, preferredRevision)

        # chrome won't respond to pings, making websockets close the connection,
        # so we disable pinging it altogether and just assume it's still alive
        transport = await websockets.client.connect(
            ws_endpoint_url, max_size=None, ping_interval=None, ping_timeout=None
        )
        self.connection = Connection(ws_endpoint_url, transport, delay=delay)
        return self.connection


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

    def __init__(self, projectRoot: str, preferredRevision: str):
        self.projectRoot = projectRoot
        self.preferredRevision = preferredRevision

    @property
    def executable_path(self):
        return resolveExecutablePath(self.projectRoot, self.preferredRevision)[0]

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

        if not executablePath:
            chrome_executable, missing_text = resolveExecutablePath(self.projectRoot, self.preferredRevision)
            if missing_text:
                raise RuntimeError(missing_text)
        else:
            chrome_executable = executablePath

        runner = BrowserRunner(chrome_executable, chrome_args, profile_path)
        runner.start(
            handleSIGINT=handleSIGINT, handleSIGHUP=handleSIGHUP, handleSIGTERM=handleSIGTERM, env=env, dumpio=dumpio
        )

        try:
            con = await runner.setupConnection()
            browser = await Browser.create(
                connection=con,
                contextIds=[],
                ignoreHTTPSErrors=ignoreHTTPSErrors,
                defaultViewport=defaultViewport,
                process=runner.proc,
                closeCallback=runner.close,
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

    async def connect(self, browserWSEndpoint: str = None, browserURL: str = None, transport: Any = None,
                      ignoreHTTPSErrors: bool = False, slowMo: float = 0, defaultViewport: Viewport = None):
        assert len([x for x in (browserWSEndpoint, browserURL, transport) if x]) == 1, \
            'exactly one of browserWSEndpoint, browserURL, transport must be specified'

        if transport:
            connection = Connection('', transport, slowMo)
        elif browserWSEndpoint:
            transport = await websockets.client.connect(
                browserWSEndpoint, max_size=None, ping_interval=None, ping_timeout=None
            )
            connection = Connection(browserWSEndpoint, transport, delay=slowMo)
        elif browserURL:
            browserWSEndpoint = getWSEndpoint(browserURL)
            transport = await websockets.client.connect(
                browserWSEndpoint, max_size=None, ping_interval=None, ping_timeout=None
            )
            connection = Connection(browserWSEndpoint, transport, delay=slowMo)

        async def close_callback():
            await connection.send('Browser.close')

        context_ids = await connection.send('Target.getBrowserContexts')
        return Browser.create(connection=connection, contextIds=context_ids, ignoreHTTPSErrors=ignoreHTTPSErrors,
                              defaultViewport=defaultViewport, process=None, closeCallback=close_callback)


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


def waitForWSEndpoint(proc: subprocess.Popen, timeout: float, preferredRevision: str):
    assert proc.stdout is not None, 'process STDOUT wasn\'t piped'
    start = time.perf_counter()
    for line in iter(proc.stdout.readline, b''):
        line = line.decode()
        if (start - time.perf_counter()) > timeout:
            raise TimeoutError(
                f'Timed out after ${timeout * 1000:.0f}ms while trying to connect to the browser! '
                f'Only Chrome at revision {preferredRevision} is guaranteed to work.'
            )
        potential_match = re.match(r'DevTools listening on (ws://.*)\r+$$', line)
        if potential_match:
            return potential_match.group(1)
    raise RuntimeError(
        'Process ended before WebSockets endpoint could be found'
        f'Only Chrome at revision {preferredRevision} is guaranteed to work.'
    )


def resolveExecutablePath(projectRoot: str, preferred_revision: str) -> Tuple[Optional[str], Optional[str]]:
    env = os.environ
    EXECUTABLE_VARS = [
        'PYPPETEER2_EXECUTABLE_PATH',
        'PYPPETEER_EXECUTABLE_PATH',
        'PUPPETEER_EXECUTABLE_PATH',
        'npm_config_puppeteer_executable_path',
        'npm_package_config_puppeteer_executable_path',
    ]
    REVISION_VARS = [
        'PYPPETEER2_CHROMIUM_REVISION',
        'PYPPETEER_CHROMIUM_REVISION',
        'PUPPETEER_CHROMIUM_REVISION',
    ]
    executable = next((env.get(x) for x in EXECUTABLE_VARS if env.get(x)), None)
    if executable:
        if not Path(executable).is_file():
            missing_txt = f'Tried to use env variables ({",".join(EXECUTABLE_VARS)}) to launch browser, but no executable was found at {executable}'
            return None, missing_txt
    browser_fetcher = BrowserFetcher(projectRoot)
    revision = next((env.get(x) for x in REVISION_VARS if env.get(x)), None)
    if revision:
        revision_info = browser_fetcher.revision_info(revision)
        if not revision_info.local:
            missing_txt = f'Tried to use env variables ({",".join(REVISION_VARS)}) to launch browser, but did not find executable at {revision_info.executable_path}'
            return None, missing_txt
    revision_info = BrowserFetcher(preferred_revision)
    if not revision_info.local:
        missing_txt = 'Browser is not downloaded. Try running pypeteer2-install'
    return revision_info.executable_path, missing_txt


def launcher(projectRoot: str = None, prefferedRevision: str = None, product: str = None):
    """Returns the appropriate browser launcher class instance"""
    env = os.environ
    PRODUCT_ENV_VARS = [
        'PUPPETEER_PRODUCT',
        'npm_config_puppeteer_product',
        'npm_package_config_puppeteer_product',
        'PYPPETEER_PRODUCT',
    ]
    product_env_vars_val = [env.get(x) for x in PRODUCT_ENV_VARS]
    product = next(x for x in [product] + product_env_vars_val if x)
    if product == 'firefox':
        return FirefoxLauncher(projectRoot, prefferedRevision)
    else:
        return ChromeLauncher(projectRoot, prefferedRevision)
