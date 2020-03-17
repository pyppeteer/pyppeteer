from syncer import sync

from pyppeteer import Pyppeteer
from .base import browser


@sync
async def test_browser_version():
    version = await browser.version()
    assert version.startswith('Headless')


@sync
async def test_browser_ua():
    ua = await browser.userAgent()
    assert 'WebKit' in ua or 'Gecko' in ua


@sync
async def test_browser_target():
    target = browser.target()
    assert target.type == 'browser'


@sync
async def test_browser_process():
    proc = browser.process
    assert proc.pid


@sync
async def test_browser_remote_process():
    browser_ws_endpoint = browser.wsEndpoint
    remote_browser = Pyppeteer().connect(browserWSEndpoint=browser_ws_endpoint)
    assert remote_browser.process.pid is None
    await remote_browser.disconnect()


@sync
async def test_browser_connected():
    browser_ws_endpoint = browser.wsEndpoint
    remote_browser = Pyppeteer().connect(browserWSEndpoint=browser_ws_endpoint)
    assert remote_browser.isConnected
    await remote_browser.disconnect()
    assert not remote_browser.isConnected
