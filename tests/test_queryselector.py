"""Pyppeteer2 uses functions which have following counterparts in original puppeteer node.js:
puppeteer 	    pyppeteer2 	                pyppeteer2 shorthand
Page.$() 	    Page.querySelector() 	    Page.J()
Page.$$() 	    Page.querySelectorAll() 	Page.JJ()
Page.$x() 	    Page.xpath() 	            Page.Jx()
Page.$eval()    Page.querySelectorEval()    Page.Jeval()
Page.$$eval()   Page.querySelectorAllEval() Page.JJeval()

"""
import pytest

from syncer import sync

from pyppeteer.errors import ElementHandleError
from tests.conftest import chrome_only


@chrome_only
@sync
async def test_page_Jeval_method(isolated_page):
    """Test Page().Jeval() aka `querySelectorEval()` method."""
    page = isolated_page
    await page.setContent('<section id="testAttribute">43543</section>')
    idAttribute_Jeval = await page.Jeval('section', "e => e.id")
    idAttribute_query_eval = await page.querySelectorEval('section', "e => e.id")
    assert idAttribute_Jeval == idAttribute_query_eval == 'testAttribute'


@chrome_only
@sync
async def test_Jeval_accepts_args(isolated_page):
    """Test Page().Jeval() should accept arguments."""
    page = isolated_page
    await page.setContent('<section>hello</section>')
    text = await page.Jeval('section', "(e, suffix) => e.textContent + suffix", ' world!')
    assert text == 'hello world!'


@chrome_only
@sync
async def test_Jeval_accepts_elementHandle(isolated_page):
    """Test Page().Jeval() should accept ElementHandle object as args."""
    page = isolated_page
    await page.setContent('<section>hello</section><div> world</div>')
    divHandle = await page.J('div')
    text = await page.Jeval('section', "(e, div) => e.textContent + div.textContent", divHandle)
    assert text == 'hello world'


@chrome_only
@sync
async def test_Jeval_throws_exception(isolated_page):
    """Test Page().Jeval() should throw error if no element is found."""
    page = isolated_page
    with pytest.raises(ElementHandleError) as exc:
        await page.Jeval('section', "e => e.id")
    assert 'Error: failed to find element matching selector "section"' in str(exc)


@chrome_only
@sync
async def test_page_JJeval_method(isolated_page):
    """Test Page().JJeval() method."""
    page = isolated_page
    await page.setContent('<div>hello</div><div>beautiful</div><div>world!</div>')
    divsCount_jjeval = await page.JJeval('div', "divs => divs.length")
    divsCount_query = await page.querySelectorAllEval('div', "divs => divs.length")
    assert divsCount_jjeval == divsCount_query == 3


@chrome_only
@sync
async def test_page_J_queries_element(isolated_page):
    """Test Page().J() method should query existing element."""
    page = isolated_page
    await page.setContent('<section>test</section>')
    element = await page.J('section')
    assert element


@chrome_only
@sync
async def test_J_returns_none_for_nonexisting_element(isolated_page):
    """Test Page().J() method should return null for non-existing element."""
    page = isolated_page
    element = await page.J('non-existing-element')
    assert not element


@chrome_only
@sync
async def test_page_JJ_queries_elements(isolated_page):
    """Test Page().JJ() method should query existing elements."""
    page = isolated_page
    await page.setContent('<div>A</div><br/><div>B</div>')
    elements = await page.JJ('div')
    assert len(elements) == 2
    assert [await page.evaluate("e => e.textContent", element) for element in elements] == ['A', 'B']


@chrome_only
@sync
async def test_page_JJ_returns_empty_array(isolated_page, server):
    """Test Page().JJ() method should return empty array if nothing is found."""
    page = isolated_page
    await page.goto(server / "empty.html")
    elements = await page.JJ('div')
    assert not elements and elements == []


@chrome_only
@sync
async def test_Jx_queries_elements(isolated_page):
    """Test Page().Jx() method should query existing elements."""
    page = isolated_page
    await page.setContent('<section>test</section>')
    elements_jx = await page.Jx('/html/body/section')
    elements_path = await page.xpath('/html/body/section')
    assert isinstance(elements_jx, list)
    assert isinstance(elements_path, list)
    assert elements_jx[0]
    assert elements_path[0]
    assert len(elements_path) == len(elements_jx) == 1


@chrome_only
@sync
async def test_Jx_returns_empty_array(isolated_page):
    """Test Page().Jx() method should return empty array for non-existing element."""
    page = isolated_page
    elements = await page.Jx('/html/body/non-existing-element')
    assert not elements and elements == []


@chrome_only
@sync
async def test_Jx_returns_multiple_elements(isolated_page):
    """Test Page().Jx() method should return multiple elements."""
    page = isolated_page
    await page.setContent('<div></div><div></div>')
    elements = await page.Jx('/html/body/div')
    assert len(elements) == 2


@sync
async def test_ElementHandle_J_queries_element(isolated_page, server):
    """Test ElementHandle.J() method should query existing element."""
    page = isolated_page
    await page.goto(server / "playground.html")
    await page.setContent('<html><body><div class="second"><div class="inner">A</div></div></body></html>')
    html = await page.J('html')
    second = await html.J('.second')
    inner = await second.J('.inner')
    content = await page.evaluate("e => e.textContent", inner)
    assert content == 'A'


@chrome_only
@sync
async def test_ElementHandle_J_returns_none_if_no_element(isolated_page):
    """Test ElementHandle.J() method should return none for non existing element."""
    page = isolated_page
    await page.setContent('<html><body><div class="second"><div class="inner">B</div></div></body></html>')
    html = await page.J('html')
    second = await html.J('.third')
    assert not second


@chrome_only
@sync
async def test_ElementHandle_Jeval_evalates_js_func(isolated_page):
    """Test ElementHandle.Jeval() method evaluates JS function against css selector."""
    page = isolated_page
    await page.setContent(
        '<html><body><div class="tweet"><div class="like">100</div><div class="retweets">10</div></div></body></html>'
    )
    tweet = await page.J('.tweet')
    content = await tweet.Jeval('.like', "node => node.innerText")
    assert content == '100'


@chrome_only
@sync
async def test_ElementHandle_Jeval_retrieves_content(isolated_page):
    """Test ElementHandle.Jeval() method should retrieve content from subtree."""
    page = isolated_page
    htmlContent = '<div class="a">not-a-child-div</div><div id="myId"><div class="a">a-child-div</div></div>'
    await page.setContent(htmlContent)
    elementHandle = await page.J('#myId')
    content = await elementHandle.Jeval('.a', "node => node.innerText")
    assert content == 'a-child-div'


# it('should throw in case of missing selector', async() = > {
#     const
# {page} = getTestState();
#
# const
# htmlContent = '<div class="a">not-a-child-div</div><div id="myId"></div>';
# await
# page.setContent(htmlContent);
# const
# elementHandle = await
# page.$('#myId');
# const
# errorMessage = await
# elementHandle.$eval('.a', node= > node.innerText).catch(error= > error.message);
# expect(errorMessage).toBe(`Error: failed
# to
# find
# element
# matching
# selector
# ".a"
# `);
# });
# });
# describeFailsFirefox('ElementHandle.$$eval', function()
# {
# it('should work', async() = > {
#     const
# {page} = getTestState();
#
# await
# page.setContent(
#     '<html><body><div class="tweet"><div class="like">100</div><div class="like">10</div></div></body></html>');
# const
# tweet = await
# page.$('.tweet');
# const
# content = await
# tweet.$$eval('.like', nodes= > nodes.map(n= > n.innerText));
# expect(content).toEqual(['100', '10']);
# });
#
# it('should retrieve content from subtree', async() = > {
#     const
# {page} = getTestState();
#
# const
# htmlContent = '<div class="a">not-a-child-div</div><div id="myId"><div class="a">a1-child-div</div><div class="a">a2-child-div</div></div>';
# await
# page.setContent(htmlContent);
# const
# elementHandle = await
# page.$('#myId');
# const
# content = await
# elementHandle.$$eval('.a', nodes= > nodes.map(n= > n.innerText));
# expect(content).toEqual(['a1-child-div', 'a2-child-div']);
# });
#
# it('should not throw in case of missing selector', async() = > {
#     const
# {page} = getTestState();
#
# const
# htmlContent = '<div class="a">not-a-child-div</div><div id="myId"></div>';
# await
# page.setContent(htmlContent);
# const
# elementHandle = await
# page.$('#myId');
# const
# nodesLength = await
# elementHandle.$$eval('.a', nodes= > nodes.length);
# expect(nodesLength).toBe(0);
# });
#
# });
#
# describeFailsFirefox('ElementHandle.$$', function()
# {
# it('should query existing elements', async() = > {
#     const
# {page} = getTestState();
#
# await
# page.setContent('<html><body><div>A</div><br/><div>B</div></body></html>');
# const
# html = await
# page.$('html');
# const
# elements = await
# html.$$('div');
# expect(elements.length).toBe(2);
# const
# promises = elements.map(element= > page.evaluate(e= > e.textContent, element));
# expect(await
# Promise.all(promises)).toEqual(['A', 'B']);
# });
#
# it('should return empty array for non-existing elements', async() = > {
#     const
# {page} = getTestState();
#
# await
# page.setContent('<html><body><span>A</span><br/><span>B</span></body></html>');
# const
# html = await
# page.$('html');
# const
# elements = await
# html.$$('div');
# expect(elements.length).toBe(0);
# });
# });
#
#
# describe('ElementHandle.$x', function()
# {
# it('should query existing element', async() = > {
#     const
# {page, server} = getTestState();
#
# await
# page.goto(server.PREFIX + '/playground.html');
# await
# page.setContent('<html><body><div class="second"><div class="inner">A</div></div></body></html>');
# const
# html = await
# page.$('html');
# const
# second = await
# html.$x(`. / body / div[contains( @
#
#
# class , 'second')]`);
# const inner = await second[0].$x(`./ div[contains( @ class, 'inner')]`);
# const content = await page.evaluate(e = > e.textContent, inner[0]);
# expect(content).toBe('A');
# });
#
# itFailsFirefox('should return null for non-existing element', async() = > {
# const {page} = getTestState();
#
# await page.setContent('<html><body><div class="second"><div class="inner">B</div></div></body></html>');
# const html = await page.$('html');
# const second = await html.$x(` / div[contains( @ class, 'third')]`);
# expect(second).toEqual([]);
