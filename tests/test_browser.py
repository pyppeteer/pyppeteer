from syncer import sync

from .base import browser

@sync
async def test_browser_version():
    version = await browser.version()
    assert len(version) > 0
    assert version.startswith('Headless')