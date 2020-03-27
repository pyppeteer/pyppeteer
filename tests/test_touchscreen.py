import pytest
from pyppeteer import devices
from syncer import sync


@pytest.fixture
def emulated_mobile_page(isolated_page):
    sync(isolated_page.emulate(**devices['iPhone 6']))
    return isolated_page


@sync
async def test_taps_button(emulated_mobile_page, server):
    await emulated_mobile_page.goto(server / 'input/button.html')
    await emulated_mobile_page.tap('button')
    assert await emulated_mobile_page.evaluate('result') == 'Clicked'


@sync
async def test_reports_touches(emulated_mobile_page, server):
    await emulated_mobile_page.goto(server / 'input/button.html')
    await emulated_mobile_page.tap('button')
    assert await emulated_mobile_page.evaluate('getResult()') == ['Touchstart: 0', 'Touchend: 0']
