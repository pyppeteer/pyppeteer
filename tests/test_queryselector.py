"""Test queryselector set of methods.
Pyppeteer uses functions which have following counterparts in original puppeteer node.js:
┌───────────────┬─────────────────────────────┬──────────────────────┐
│   puppeteer   │         pyppeteer           │ pyppeteer shorthand  │
├───────────────┼─────────────────────────────┼──────────────────────┤
│ Page.$()      │ Page.querySelector()        │ Page.J()             │
│ Page.$$()     │ Page.querySelectorAll()     │ Page.JJ()            │
│ Page.$x()     │ Page.xpath()                │ Page.Jx()            │
│ Page.$eval()  │ Page.querySelectorEval()    │ Page.Jeval()         │
│ Page.$$eval() │ Page.querySelectorAllEval() │ Page.JJeval()        │
└───────────────┴─────────────────────────────┴──────────────────────┘

"""
import pytest

from syncer import sync

from pyppeteer.errors import ElementHandleError
from tests.conftest import chrome_only


class TestPageJeval:

    @chrome_only
    @sync
    async def test_Jeval_executes_js_func(self, isolated_page):
        """Test Page().Jeval() aka `querySelectorEval()` method,
        which executes JS function with an element which matches ``selector``

        """
        page = isolated_page
        await page.setContent('<section id="testAttribute">43543</section>')
        idAttributeJeval = await page.Jeval('section', "e => e.id")
        assert idAttributeJeval == 'testAttribute'
        # verify alias is the same method
        assert page.Jeval == page.querySelectorEval

    @chrome_only
    @sync
    async def test_Jeval_accepts_args(self, isolated_page):
        """Test Page().Jeval() should accept arguments."""
        page = isolated_page
        await page.setContent('<section>hello</section>')
        text = await page.Jeval('section', "(e, suffix) => e.textContent + suffix", ' world!')
        assert text == 'hello world!'

    @chrome_only
    @sync
    async def test_Jeval_accepts_elementHandle(self, isolated_page):
        """Test Page().Jeval() should accept ElementHandle object as args."""
        page = isolated_page
        await page.setContent('<section>hello</section><div> world</div>')
        divHandle = await page.J('div')
        text = await page.Jeval('section', "(e, div) => e.textContent + div.textContent", divHandle)
        assert text == 'hello world'

    @chrome_only
    @sync
    async def test_Jeval_throws_exc_if_no_element(self, isolated_page):
        """Test Page().Jeval() should throw error if no element is found."""
        page = isolated_page
        with pytest.raises(ElementHandleError, match='Error: failed to find element matching selector "section"'):
            await page.Jeval('section', "e => e.id")


class TestPageJJeval:

    @chrome_only
    @sync
    async def test_JJeval_executes_js_func(self, isolated_page):
        """Test Page().JJeval() method executes JS function
        with all elements which matches ``selector``.

        """
        page = isolated_page
        await page.setContent('<div>hello</div><div>beautiful</div><div>world!</div>')
        divsCountJJeval = await page.JJeval('div', "divs => divs.length")
        assert divsCountJJeval == 3
        # verify alias is the same method
        assert page.JJeval == page.querySelectorAllEval


class TestPageJ:

    @chrome_only
    @sync
    async def test_J_queries_element(self, isolated_page):
        """Test Page().J() method should query existing element."""
        page = isolated_page
        await page.setContent('<section>test</section>')
        element = await page.J('section')
        assert element
        # verify alias is the same method
        assert page.J == page.querySelector

    @chrome_only
    @sync
    async def test_J_returns_none_if_no_element(self, isolated_page):
        """Test Page().J() method should return null for non-existing element."""
        page = isolated_page
        element = await page.J('non-existing-element')
        assert element is None


class TestPageJJ:

    @chrome_only
    @sync
    async def test_JJ_queries_elements(self, isolated_page):
        """Test Page().JJ() method should query existing elements."""
        page = isolated_page
        await page.setContent('<div>A</div><br/><div>B</div>')
        elements = await page.JJ('div')
        assert len(elements) == 2
        assert [await page.evaluate("e => e.textContent", element) for element in elements] == ['A', 'B']
        # verify alias is the same method
        assert page.JJ == page.querySelectorAll

    @chrome_only
    @sync
    async def test_JJ_returns_empty_list_if_no_element(self, isolated_page, server):
        """Test Page().JJ() method should return empty list if nothing is found."""
        page = isolated_page
        await page.goto(server / "empty.html")
        elements = await page.JJ('div')
        assert elements == []


class TestPageJx:

    @chrome_only
    @sync
    async def test_Jx_queries_elements(self, isolated_page):
        """Test Page().Jx() method should query existing elements."""
        page = isolated_page
        await page.setContent('<section>test</section>')
        elementsJx = await page.Jx('/html/body/section')
        assert isinstance(elementsJx, list)
        assert elementsJx[0]
        assert len(elementsJx) == 1
        # verify alias is the same method
        assert page.xpath == page.Jx

    @chrome_only
    @sync
    async def test_Jx_returns_empty_list_if_no_element(self, isolated_page):
        """Test Page().Jx() method should return empty list for non-existing element."""
        page = isolated_page
        elements = await page.Jx('/html/body/non-existing-element')
        assert elements == []

    @chrome_only
    @sync
    async def test_Jx_returns_multiple_elements(self, isolated_page):
        """Test Page().Jx() method should return multiple elements."""
        page = isolated_page
        await page.setContent('<div></div><div></div>')
        elements = await page.Jx('/html/body/div')
        assert len(elements) == 2


class TestElementHandleJ:

    @sync
    async def test_J_queries_element(self, isolated_page, server):
        """Test ElementHandle.J() method should query existing element."""
        page = isolated_page
        await page.goto(server / "playground.html")
        await page.setContent('<html><body><div class="second"><div class="inner">A</div></div></body></html>')
        html = await page.J('html')
        second = await html.J('.second')
        inner = await second.J('.inner')
        content = await page.evaluate("e => e.textContent", inner)
        assert content == 'A'
        # verify alias is the same method
        assert second.J == second.querySelector

    @chrome_only
    @sync
    async def test_J_returns_none_if_no_element(self, isolated_page):
        """Test ElementHandle.J() method should return none for non existing element."""
        page = isolated_page
        await page.setContent('<html><body><div class="second"><div class="inner">B</div></div></body></html>')
        html = await page.J('html')
        second = await html.J('.third')
        assert second is None


class TestElementHandleJeval:

    @chrome_only
    @sync
    async def test_Jeval_evalates_js_func(self, isolated_page):
        """Test ElementHandle.Jeval() method evaluates JS function against css selector."""
        page = isolated_page
        await page.setContent(
            '<html><body><div class="tweet"><div class="like">100</div>'
            '<div class="retweets">10</div></div></body></html>'
        )
        tweet = await page.J('.tweet')
        content = await tweet.Jeval('.like', "node => node.innerText")
        assert content == '100'
        # verify alias is the same method
        assert tweet.Jeval == tweet.querySelectorEval

    @chrome_only
    @sync
    async def test_Jeval_retrieves_content(self, isolated_page):
        """Test ElementHandle.Jeval() method should retrieve content from subtree."""
        page = isolated_page
        htmlContent = '<div class="a">not-a-child-div</div><div id="myId"><div class="a">a-child-div</div></div>'
        await page.setContent(htmlContent)
        elementHandle = await page.J('#myId')
        content = await elementHandle.Jeval('.a', "node => node.innerText")
        assert content == 'a-child-div'

    @chrome_only
    @sync
    async def test_Jeval_raises_exc_if_no_selector(self, isolated_page):
        """Test ElementHandle.Jeval() throws exception in case of missing selector."""
        page = isolated_page
        htmlContent = '<div class="a">not-a-child-div</div><div id="myId"></div>'
        await page.setContent(htmlContent)
        elementHandle = await page.J('#myId')
        with pytest.raises(ElementHandleError, match='Error: failed to find element matching selector ".a"'):
            await elementHandle.Jeval('.a', "node => node.innerText")


class TestElementHandleJJeval:

    @chrome_only
    @sync
    async def test_JJeval_executes_js_func(self, isolated_page):
        """Test ElementHandle.JJeval() should execute JS function."""
        page = isolated_page
        await page.setContent(
            '<html><body><div class="tweet"><div class="like">100</div><div class="like">10</div></div></body></html>'
        )
        tweet = await page.J('.tweet')
        content = await tweet.JJeval('.like', "nodes => nodes.map(n => n.innerText)")
        assert content == ['100', '10']
        # verify alias is the same method
        assert tweet.JJeval == tweet.querySelectorAllEval

    @chrome_only
    @sync
    async def test_JJeval_retrieves_content(self, isolated_page):
        """Test ElementHandle.JJeval() should retrieve content from subtree."""
        page = isolated_page
        htmlContent = \
            '<div class="a">not-a-child-div</div><div id="myId">' \
            '<div class="a">a1-child-div</div><div class="a">a2-child-div</div></div>'
        await page.setContent(htmlContent)
        elementHandle = await page.J('#myId')
        content = await elementHandle.JJeval('.a', "nodes => nodes.map(n => n.innerText)")
        assert content == ['a1-child-div', 'a2-child-div']

    @chrome_only
    @sync
    async def test_JJeval_returns_empty_list_if_no_selector(self, isolated_page):
        """Test ElementHandle.JJeval() should return an empty list
        and doesn't raises exception in case of missing selector.

        """
        page = isolated_page
        htmlContent = '<div class="a">not-a-child-div</div><div id="myId"></div>'
        await page.setContent(htmlContent)
        elementHandle = await page.J('#myId')
        nodesLength = await elementHandle.JJeval('.a', "nodes => nodes.length")
        assert nodesLength == 0


class TestElementHandleJJ:

    @chrome_only
    @sync
    async def test_JJ_queries_elements(self, isolated_page):
        """Test ElementHandle.JJ() should query existing elements."""
        page = isolated_page
        await page.setContent('<html><body><div>A</div><br/><div>B</div></body></html>')
        html = await page.J('html')
        elements = await html.JJ('div')
        assert len(elements) == 2
        assert [await page.evaluate("e => e.textContent", element) for element in elements] == ['A', 'B']
        # verify alias is the same method
        assert html.JJ == html.querySelectorAll

    @chrome_only
    @sync
    async def test_JJ_returns_empty_list_if_no_element(self, isolated_page):
        """Test ElementHandle.JJ() should return empty array for non-existing elements."""
        page = isolated_page
        await page.setContent('<html><body><span>A</span><br/><span>B</span></body></html>')
        html = await page.J('html')
        elements = await html.JJ('div')
        assert elements == []


class TestElementHandleJx:

    @sync
    async def test_Jx_queries_element(self, isolated_page, server):
        """Test ElementHandle.Jx() should query existing element."""
        page = isolated_page
        await page.goto(server / 'playground.html')
        await page.setContent('<html><body><div class="second"><div class="inner">A</div></div></body></html>')
        html = await page.J('html')
        second = await html.Jx("./body/div[contains(@class , 'second')]")
        inner = await second[0].Jx("./div[contains(@class, 'inner')]")
        content = await page.evaluate("e => e.textContent", inner[0])
        assert content == 'A'
        # verify alias is the same method
        assert html.Jx == html.xpath

    @sync
    @chrome_only
    async def test_Jx_returns_none_if_no_element(self, isolated_page):
        """Test ElementHandle.Jx() should return None for non-existing element."""
        page = isolated_page
        await page.setContent('<html><body><div class="second"><div class="inner">B</div></div></body></html>')
        html = await page.J('html')
        second = await html.Jx("/div[contains(@class, 'third')]")
        assert second == []
