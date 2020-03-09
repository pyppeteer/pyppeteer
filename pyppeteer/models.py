"""Type definitions for widely used types"""
try:
    from typing import TypedDict, Sequence, Union, Literal, Dict
except ImportError:
    from typing import TypedDict


class Viewport(TypedDict, total=False):
    width: float
    height: float
    deviceScaleFactor: float
    isMobile: bool
    isLandscape: bool
    hasTouch: bool


class BrowserOptions(TypedDict, total=False):
    ignoreHTTPSErrors: bool
    defaultViewport: Viewport
    slowMo: float


class ChromeArgOptions(TypedDict, total=False):
    headless: bool
    args: Sequence[str]
    userDataDir: str
    devtools: bool


class LaunchOptions(TypedDict, total=False):
    executablePath: str
    ignoreDefaultArgs: Union[Literal[False], Sequence[str]]
    handleSIGINT: bool
    handleSIGTERM: bool
    handleSIGHUP: bool
    timeout: float
    dumpio: bool
    env: Dict[str, Union[str, bool]]
