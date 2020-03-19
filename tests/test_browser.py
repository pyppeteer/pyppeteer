from syncer import sync

from pyppeteer import connect


@sync
async def test_browser_version(shared_browser):
    version = await shared_browser.version()
    assert version.startswith('Headless')


@sync
async def test_browser_ua(shared_browser):
    ua = await shared_browser.userAgent()
    assert 'WebKit' in ua or 'Gecko' in ua


@sync
async def test_browser_target(shared_browser):
    target = shared_browser.target
    assert target.type == 'browser'


@sync
async def test_browser_process(shared_browser):
    proc = shared_browser.process
    assert proc.pid


@sync
async def test_browser_remote_process(shared_browser):
    browser_ws_endpoint = shared_browser.wsEndpoint
    remote_browser = await connect(browserWSEndpoint=browser_ws_endpoint)
    assert remote_browser.process is None
    await remote_browser.disconnect()


@sync
async def test_browser_connected(shared_browser):
    browser_ws_endpoint = shared_browser.wsEndpoint
    remote_browser = await connect(browserWSEndpoint=browser_ws_endpoint)
    assert remote_browser.isConnected
    await remote_browser.disconnect()
    assert not remote_browser.isConnected
