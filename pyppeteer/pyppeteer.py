from typing import Dict, Any

from pyppeteer.browser import Browser
from pyppeteer.device_descriptors import devices
from pyppeteer.launcher import Launcher
from pyppeteer.browser_fetcher import BrowserFetcher

class Pyppeteer:
    def __init__(self, projectRoot: str, preferredRevision: str):
        self._projectRoot = projectRoot
        self._preferredRevision = preferredRevision
        self._lazyLauncher = None
        self.productName = None

    @property
    def executablePath(self):
        return self._launcher.executablePath

    @property
    def product(self):
        return self._launcher.product

    @property
    def devices(self):
        return devices

    def launch(self, options: Dict[str, Any] = None) -> Browser:
        if not self.productName and options:
            self.productName = options.get('product')
        return self._launcher.launch(options)

    def connect(self, options: Any):
        return self._launcher.connect(options)

    @property
    async def _launcher(self):
        if not self._lazyLauncher:
            self._lazyLauncher = Launcher(
                projectRoot=self._projectRoot,
                preferredRevision=self._preferredRevision,
                product=self.productName
            )
        return self._lazyLauncher

    async def defaultArgs(self, options: Any):
        return self._launcher.defaultArgs(options)

    def createBrowserFetcher(self, options: Any):
        return BrowserFetcher(projectRoot=self._projectRoot, options=options)
