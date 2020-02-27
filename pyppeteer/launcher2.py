import os
from pathlib import Path
from typing import Dict, Sequence, Union, TypedDict, List


class BrowserRunner:
    def __init__(self, executable_path: str, process_args: Sequence[str],
                 temp_dir: Union[Path, str]):  # todo: proper typing
        self.executable_path = executable_path
        self.process_runner = list(process_args) if not isinstance(process_args, list) else process_args
        self.temp_dir = temp_dir

        self.proc = None
        self.connection = None

        self._closed = True
        self._listeners = []


def launcher(projectRoot: str = None, prefferedRevision: str = None, product: str = None):
    """Returns the appropriate browser launcher class instance"""
    env = os.environ
    product = product or env.get('PYPPETEER_PRODUCT')
    if product == 'firefox':
        return FirefoxLauncher(projectRoot, prefferedRevision)
    else:
        return ChromeLauncher(projectRoot, prefferedRevision)


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
    timeout: Union[int, float]
    dumpio: bool
    env: Dict[str, Union[str, bool]]


class BrowserOptions(TypedDict):
    ignoreHTTPSErrors: bool
