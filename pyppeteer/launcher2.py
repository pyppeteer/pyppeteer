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
        if not kwargs.get('dumpio'):
            # we read stdout to check it for the ws endpoint
            process_opts['stdout'] = subprocess.PIPE
            process_opts['stderr'] = subprocess.STDOUT
        else:
            # todo: dumpio. See: https://pptr.dev/#?product=Puppeteer&version=v2.1.1&show=api-puppeteerlaunchoptions
            # we need to tee proc stdout to both PIPE (so we can read it) and stdout (so users can see dumped IO)
            # see these SO threads:
            # https://stackoverflow.com/q/2996887/
            # https://stackoverflow.com/q/17190221/
            raise NotImplementedError(f'dumpio argument currently not implemented')

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


class BaseBrowserLauncher:
    def __init__(self, projectRoot: str, preferredRevision: str):
        self.projectRoot = projectRoot
        self.preferredRevision = preferredRevision

    async def connect(
        self,
        browserWSEndpoint: str = None,
        browserURL: str = None,
        transport: Any = None,
        ignoreHTTPSErrors: bool = False,
        slowMo: float = 0,
        defaultViewport: Viewport = None,
    ):
        assert (
            len([x for x in (browserWSEndpoint, browserURL, transport) if x]) == 1
        ), 'exactly one of browserWSEndpoint, browserURL, transport must be specified'

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
        return Browser.create(
            connection=connection,
            contextIds=context_ids,
            ignoreHTTPSErrors=ignoreHTTPSErrors,
            defaultViewport=defaultViewport,
            process=None,
            closeCallback=close_callback,
        )


class ChromeLauncher(BaseBrowserLauncher):
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
        super().__init__(projectRoot, preferredRevision)

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
            chrome_args.extend(self.default_args(**kwargs))
        elif isinstance(ignoreDefaultArgs, list):
            chrome_args.extend(
                [x for x in self.default_args(**kwargs) if x not in ignoreDefaultArgs]
            )
        else:
            chrome_args.extend(args)

        if not any(x.startswith('--remote-debugging-') for x in chrome_args):
            chrome_args.append(f'--remote-debugging-port={get_free_port()}')
        if not any(x.startswith(f'--user-data-dir') for x in chrome_args):
            profile_path = tempfile.TemporaryDirectory(prefix='pyppeteer2_chrome_profile_')
            chrome_args.append(f'--user-data-dir={profile_path.name}')

        if not executablePath:
            chrome_executable, missing_text = resolveExecutablePath(
                self.projectRoot, self.preferredRevision
            )
            if missing_text:
                raise RuntimeError(missing_text)
        else:
            chrome_executable = executablePath

        runner = BrowserRunner(chrome_executable, chrome_args, profile_path)
        runner.start(
            handleSIGINT=handleSIGINT,
            handleSIGHUP=handleSIGHUP,
            handleSIGTERM=handleSIGTERM,
            env=env,
            dumpio=dumpio,
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
            await browser.waitForTarget(lambda x: x.type == 'page')
            return browser
        finally:
            try:
                runner.kill()
            except Exception:
                pass

    def default_args(
        self,
        args: List[str] = None,
        devtools: bool = False,
        headless: bool = True,
        userDataDir: str = None,
    ):
        chrome_args = self.DEFAULT_ARGS[:]
        if userDataDir:
            chrome_args.append(f'--user-data-dir={userDataDir}')
        if devtools:
            chrome_args.append('--auto-open-devtools-for-tabs')
        if headless:
            chrome_args.extend(['--headless', '--hide-scrollbars', '--mute-audio'])
        if all(x.startswith('-') for x in args):
            chrome_args.append('about:blank')
        if isinstance(args, Sequence):
            chrome_args.extend(args)
        return chrome_args


class FirefoxLauncher(BaseBrowserLauncher):
    DEFAULT_ARGS = [
        '--remote-debugging-port=0',
        '--no-remote',
        '--foreground',
    ]
    _server = 'dummy.test'
    DEFAULT_PROFILE_PREFS = {
        # Make sure Shield doesn't hit the network.
        'app.normandy.api_url': '',
        # Disable Firefox old build background check
        'app.update.checkInstallTime': False,
        # Disable automatically upgrading Firefox
        'app.update.disabledForTesting': True,
        # Increase the APZ content response timeout to 2 minute
        'apz.content_response_timeout': 60000,
        # Prevent various error message on the console
        # jest-puppeteer asserts that no error message is emitted by the console
        'browser.contentblocking.features.standard': '-tp,tpPrivate,cookieBehavior0,-cm,-fp',
        # Enable the dump function: which sends messages to the system
        # console
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1543115
        'browser.dom.window.dump.enabled': True,
        # Disable topstories
        'browser.newtabpage.activity-stream.feeds.section.topstories': False,
        # Always display a blank page
        'browser.newtabpage.enabled': False,
        # Background thumbnails in particular cause grief: and disabling
        # thumbnails in general cannot hurt
        'browser.pagethumbnails.capturing_disabled': True,
        # Disable safebrowsing components.
        'browser.safebrowsing.blockedURIs.enabled': False,
        'browser.safebrowsing.downloads.enabled': False,
        'browser.safebrowsing.malware.enabled': False,
        'browser.safebrowsing.passwords.enabled': False,
        'browser.safebrowsing.phishing.enabled': False,
        # Disable updates to search engines.
        'browser.search.update': False,
        # Do not restore the last open set of tabs if the browser has crashed
        'browser.sessionstore.resume_from_crash': False,
        # Skip check for default browser on startup
        'browser.shell.checkDefaultBrowser': False,
        # Disable newtabpage
        'browser.startup.homepage': 'about:blank',
        # Do not redirect user when a milstone upgrade of Firefox is detected
        'browser.startup.homepage_override.mstone': 'ignore',
        # Start with a blank page about:blank
        'browser.startup.page': 0,
        # Do not allow background tabs to be zombified on Android: otherwise for
        # tests that open additional tabs: the test harness tab itself might get
        # unloaded
        'browser.tabs.disableBackgroundZombification': False,
        # Do not warn when closing all other open tabs
        'browser.tabs.warnOnCloseOtherTabs': False,
        # Do not warn when multiple tabs will be opened
        'browser.tabs.warnOnOpen': False,
        # Disable the UI tour.
        'browser.uitour.enabled': False,
        # Turn off search suggestions in the location bar so as not to trigger
        # network connections.
        'browser.urlbar.suggest.searches': False,
        # Disable first run splash page on Windows 10
        'browser.usedOnWindows10.introURL': '',
        # Do not warn on quitting Firefox
        'browser.warnOnQuit': False,
        # Do not show datareporting policy notifications which can
        # interfere with tests
        'datareporting.healthreport.about.reportUrl': f'http://{_server}/dummy/abouthealthreport/',
        'datareporting.healthreport.documentServerURI': f'http://{_server}/dummy/healthreport/',
        'datareporting.healthreport.logging.consoleEnabled': False,
        'datareporting.healthreport.service.enabled': False,
        'datareporting.healthreport.service.firstRun': False,
        'datareporting.healthreport.uploadEnabled': False,
        'datareporting.policy.dataSubmissionEnabled': False,
        'datareporting.policy.dataSubmissionPolicyAccepted': False,
        'datareporting.policy.dataSubmissionPolicyBypassNotification': True,
        # DevTools JSONViewer sometimes fails to load dependencies with its require.js.
        # This doesn't affect Puppeteer but spams console (Bug 1424372)
        'devtools.jsonview.enabled': False,
        # Disable popup-blocker
        'dom.disable_open_during_load': False,
        # Enable the support for File object creation in the content process
        # Required for |Page.setFileInputFiles| protocol method.
        'dom.file.createInChild': True,
        # Disable the ProcessHangMonitor
        'dom.ipc.reportProcessHangs': False,
        # Disable slow script dialogues
        'dom.max_chrome_script_run_time': 0,
        'dom.max_script_run_time': 0,
        # Only load extensions from the application and user profile
        # AddonManager.SCOPE_PROFILE + AddonManager.SCOPE_APPLICATION
        'extensions.autoDisableScopes': 0,
        'extensions.enabledScopes': 5,
        # Disable metadata caching for installed add-ons by default
        'extensions.getAddons.cache.enabled': False,
        # Disable installing any distribution extensions or add-ons.
        'extensions.installDistroAddons': False,
        # Disabled screenshots extension
        'extensions.screenshots.disabled': True,
        # Turn off extension updates so they do not bother tests
        'extensions.update.enabled': False,
        # Turn off extension updates so they do not bother tests
        'extensions.update.notifyUser': False,
        # Make sure opening about:addons will not hit the network
        'extensions.webservice.discoverURL': f'http://{_server}/dummy/discoveryURL',
        # Allow the application to have focus even it runs in the background
        'focusmanager.testmode': True,
        # Disable useragent updates
        'general.useragent.updates.enabled': False,
        # Always use network provider for geolocation tests so we bypass the
        # macOS dialog raised by the corelocation provider
        'geo.provider.testing': True,
        # Do not scan Wifi
        'geo.wifi.scan': False,
        # No hang monitor
        'hangmonitor.timeout': 0,
        # Show chrome errors and warnings in the error console
        'javascript.options.showInConsole': True,
        # Disable download and usage of OpenH264: and Widevine plugins
        'media.gmp-manager.updateEnabled': False,
        # Prevent various error message on the console
        # jest-puppeteer asserts that no error message is emitted by the console
        'network.cookie.cookieBehavior': 0,
        # Do not prompt for temporary redirects
        'network.http.prompt-temp-redirect': False,
        # Disable speculative connections so they are not reported as leaking
        # when they are hanging around
        'network.http.speculative-parallel-limit': 0,
        # Do not automatically switch between offline and online
        'network.manage-offline-status': False,
        # Make sure SNTP requests do not hit the network
        'network.sntp.pools': _server,
        # Disable Flash.
        'plugin.state.flash': 0,
        'privacy.trackingprotection.enabled': False,
        # Enable Remote Agent
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1544393
        'remote.enabled': True,
        # Don't do network connections for mitm priming
        'security.certerrors.mitm.priming.enabled': False,
        # Local documents have access to all other local documents,
        # including directory listings
        'security.fileuri.strict_origin_policy': False,
        # Do not wait for the notification button security delay
        'security.notification_enable_delay': 0,
        # Ensure blocklist updates do not hit the network
        'services.settings.server': f'http://{_server}/dummy/blocklist/',
        # Do not automatically fill sign-in forms with known usernames and
        # passwords
        'signon.autofillForms': False,
        # Disable password capture, so that tests that include forms are not
        # influenced by the presence of the persistent doorhanger notification
        'signon.rememberSignons': False,
        # Disable first-run welcome page
        'startup.homepage_welcome_url': 'about:blank',
        # Disable first-run welcome page
        'startup.homepage_welcome_url.additional': '',
        # Disable browser animations (tabs, fullscreen, sliding alerts)
        'toolkit.cosmeticAnimations.enabled': False,
        # We want to collect telemetry, but we don't want to send in the results
        'toolkit.telemetry.server': f'https://{_server}/dummy/telemetry/',
        # Prevent starting into safe mode after application crashes
        'toolkit.startup.max_resumed_crashes': -1,
    }
    product = 'firefox'

    def __init__(self, projectRoot: str, preferredRevision: str):
        super().__init__(projectRoot, preferredRevision)

    async def launch(self):
        pass

    def default_args(
        self,
        args: List[str] = None,
        devtools: bool = False,
        headless: bool = True,
        userDataDir: str = None,
    ):
        proc_args = self.DEFAULT_ARGS[:]
        proc_args.extend(args)
        if userDataDir:
            proc_args.extend(['--profile', userDataDir])
        if headless:
            proc_args.append('--headless')
        if devtools:
            proc_args.append('--devtools')
        if all(x.startswith('-') for x in args):
            proc_args.append('about:blank')
        return proc_args

    async def _create_profile(self, **kwargs) -> tempfile.TemporaryDirectory:
        profile_path = tempfile.TemporaryDirectory(prefix='pyppeteer2_firefox_profile')
        prefs = {**self.DEFAULT_PROFILE_PREFS, **kwargs}
        serialized_prefs = [
            f'user_pref({json.dumps(key)}, {json.dumps(val)}' for key, val in prefs.items()
        ]
        with open(Path(profile_path.name).joinpath('user.js'), 'w') as user:
            user.write('\n'.join(serialized_prefs))
        return profile_path


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
                f'Timed out after {timeout * 1000:.0f}ms while trying to connect to the browser! '
                f'Only Chrome at revision {preferredRevision} is guaranteed to work.'
            )
        potential_match = re.match(r'DevTools listening on (ws://.*)\r+$$', line)
        if potential_match:
            return potential_match.group(1)
    raise RuntimeError(
        'Process ended before WebSockets endpoint could be found'
        f'Only Chrome at revision {preferredRevision} is guaranteed to work.'
    )


def resolveExecutablePath(
    projectRoot: str, preferred_revision: str
) -> Tuple[Optional[str], Optional[str]]:
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
