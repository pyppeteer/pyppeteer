import os
from pathlib import Path
from typing import Dict, Sequence, Union, TypedDict, List, Optional

from pyppeteer.util import merge_dict

Number = Union[int, float]

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
    timeout: Number
    dumpio: bool
    env: Dict[str, Union[str, bool]]

class Viewport(TypedDict):
    width: Number
    height: Number
    deviceScaleFactor: Optional[Number]
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
        self.process_runner = list(process_args) if not isinstance(process_args, list) else process_args
        self.temp_dir = Path(temp_dir) if isinstance(temp_dir, str) else temp_dir

        self.proc = None
        self.connection = None

        self._closed = True
        self._listeners = []

    def start(self, options: LaunchOptions, **kwargs: LaunchOptions):
        options = merge_dict(options, kwargs)
        if options.get('pipe'):
            raise NotImplementedError('Communication via pipe not supported')
        if options.get('dumpio'):
            pass
        else:
            pass
        assert self.proc is None, 'This process has previously been started'


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
