from pyppeteer.browser_fetcher import BrowserFetcher


def test_can_download():
    fetcher = BrowserFetcher()
    assert fetcher.can_download("588429")
    assert not fetcher.can_download("-1")
