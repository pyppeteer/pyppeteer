from asyncio import gather
import pytest
from syncer import sync

from pyppeteer.errors import NetworkError, BrowserError
from pyppeteer import devices
from tests.utils import attachFrame


@sync
async def test_click_button(isolated_page, server):
    """shoud click the button"""
    await isolated_page.goto(server / 'input/button.html')
    await isolated_page.click('button')
    assert await isolated_page.evaluate('() => result') == 'Clicked'


@sync
async def test_click_svg(isolated_page, server):
    """should click svg"""
    page = isolated_page
    await page.setContent("""
    <svg height="100" width="100">
          <circle onclick="javascript:window.CLICKED=42" cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />
        </svg>
    """)
    await page.click('circle')
    assert await page.evaluate('() => window.CLICKED') == 42


@sync
async def test_click_button_window_node(isolated_page, server):
    p = isolated_page
    await p.goto(server / 'input/button.html')
    await p.evaluate('() => delete window.Node')
    await p.click('button')
    assert await p.evaluate('() => result') == 'Clicked'


@sync
async def test_click_inline_span(isolated_page, server):
    p = isolated_page
    await p.setContent("""
        <style>
        span::before {
          content: 'q';
        }
        </style>
        <span onclick='javascript:window.CLICKED=42'></span>
    """)
    await p.click('span')
    assert await p.evaluate('() => window.CLICKED') == 42


@sync
async def test_click_page_close(isolated_page, server):
    """Raise error if page is closed before click"""
    p = await isolated_page.browser.newPage()
    with pytest.raises(NetworkError):
        await gather(
            p.close(),
            p.mouse.click(1, 2)
        )


@sync
async def test_click_after_nav(isolated_page, server):
    """click after navigation"""
    p = isolated_page
    await p.goto(server / '/input/button.html')
    await p.click('button')
    await p.goto(server / '/input/button.html')
    await p.click('button')
    assert await p.evaluate('() => result') == 'Clicked'


@sync
async def test_click_no_js(isolated_page, server):
    """click when js is disabled"""
    p = isolated_page
    await p.setJavaScriptEnabled(False)
    await p.goto(server / '/wrappedlink.html')
    await gather(
        p.click('a'),
        p.waitForNavigation()
    )
    assert p.url == server / '/wrappedlink.html#clicked'


@sync
async def test_click_outside(isolated_page, server):
    """click when one of inline box children is outside of viewport"""
    p = isolated_page
    await p.setContent(
        """
        <style>
        i {
          position: absolute;
          top: -1000px;
        }
        </style>
        <span onclick='javascript:window.CLICKED = 42;'><i>woof</i><b>doggo</b></span>
        """
    )
    await p.click('span')
    assert await p.evaluate('() => window.CLICKED') == 42


@sync
async def test_triple_click(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/textarea.html')
    await p.focus('textarea')
    text = 'This is the text that we are going to try to select. Let\'s see how it goes.'
    await p.keyboard.type(text)
    await p.click('textarea')
    await p.click('textarea', clickCount=2)
    await p.click('textarea', clickCount=3)
    assert await p.evaluate("""() => {
    const textarea = document.querySelector('textarea');
    return textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    }""") == text


@sync
async def test_offscreen_button(isolated_page, server):
    """should click offscreen buttons"""
    p = isolated_page
    await p.goto(server / 'offscreenbuttons.html')

    messages = []

    def append_msg(m):
        nonlocal messages
        messages.append(m)

    p.on('console', append_msg)
    for i in range(11):
        await p.evaluate('() => window.scrollTo(0, 0)')
        await p.click(f'#btn{i}')
    assert [m.text for m in messages] == [f'button #{i} clicked' for i in range(11)]


@sync
async def test_click_checkbox(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/checkbox.html')
    assert await p.evaluate('() => result.check') is None
    await p.click('input#agree')
    assert await p.evaluate('() => result.check') is True
    assert await p.evaluate('() => result.events') == [
        'mouseover',
        'mouseenter',
        'mousemove',
        'mousedown',
        'mouseup',
        'click',
        'input',
        'change',
    ]
    await p.click('input#agree')
    assert await p.evaluate('() => result.check') is False


@sync
async def test_click_checkbox_label_toggle(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/checkbox.html')
    assert await p.evaluate('() => result.check') is None
    await p.click('label[for="agree"]')
    assert await p.evaluate('() => result.check') is True
    assert await p.evaluate('() => result.events') == ['click', 'input', 'change']
    await p.click('label[for="agree"]')
    assert await p.evaluate('() => result.check') is False


@sync
async def test_click_fail_missing_button(isolated_page, server):
    """should fail if button is missing"""
    p = isolated_page
    await p.goto(server / '/input/button.html')
    error = None
    with pytest.raises(BrowserError) as e:
        await p.click('button.does-not-exist')
        assert e.value == 'No node found for selector: button.does-not-exist'


@sync
async def test_click_no_hang_with_touch_enabled(isolated_page, server):
    """should not hang with touch-enabled viewports"""
    p = isolated_page
    await p.setViewport(devices['iPhone 6']['viewport'])
    await p.mouse.down()
    await p.mouse.move(100, 10)
    await p.mouse.up()


@sync
async def test_scroll_and_click(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/scrollable.html')
    await p.click('#button-5')
    assert await p.evaluate('() => document.querySelector("#button-5").textContent') == 'clicked'


@sync
async def test_double_click(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/button.html')
    await p.evaluate("""
        window.double = false;
        const button = document.querySelector('button');
        button.addEventListener('dblclick', event => {
          window.double = true;
        });
    """
                     )
    button = await p.J('button')
    await button.click(clickCount=2)
    assert await p.evaluate('double') == True
    assert await p.evaluate('result') == 'Clicked'


@sync
async def test_click_partially_obscured_button(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/button.html')
    await p.evaluate("""
    () => {
        const button = document.querySelector('button');
        button.textContent = 'Some really long text that will go offscreen';
        button.style.position = 'absolute';
        button.style.left = '368px';
    }
    """)
    await p.click('button')
    assert await p.evaluate('() => window.result') == 'Clicked'


@sync
async def test_click_rotated_button(isolated_page, server):  # line 215 in pup
    p = isolated_page
    await p.goto(server / '/input/rotatedButton.html')
    await p.click('button')
    assert await p.evaluate('() => result') == 'Clicked'


@sync
async def test_right_click_contextmenu_event(isolated_page, server):
    p = isolated_page
    await p.goto(server / '/input/scrollable.html')
    await p.click('#button-8', button='right')
    assert await p.evaluate(
        "() => document.querySelector('#button-8').textContent"
    ) == 'context menu'


@sync
async def test_click_links_causing_navigation(isolated_page, server):
    p = isolated_page
    await p.setContent(
        f"""<a href = "{server.empty_page}" > empty.html </a>"""
    )
    # this await should not hang
    await p.click('a')


@sync
async def test_click_button_inside_iframe(isolated_page, server):
    p = isolated_page
    await p.goto(server.empty_page)
    await p.setContent('<div style="width:100px;height:100px">spacer</div>')
    await attachFrame(p, server / '/input/button.html', 'button-test')
    frame = p.frames[1]
    button = await frame.J('button')
    await button.click()
    assert await frame.evaluate("() => window.result") == 'Clicked'


@sync
@pytest.mark.skip('skipped in upstream puppeteer')
async def test_fixed_button_inside_iframe(isolated_page, server):
    p = isolated_page
    await p.goto(server.empty_page)
    await p.setViewport(dict(width=500, height=500))
    await p.setContent('<div style="width:100px;height:2000px">spacer</div>')
    await attachFrame(p, server.cross_process_server / '/input/button.html', 'button-test')
    frame = p.frames[1]
    await frame.evaluate(
        'button',
        "button => button.style.setProperty('position', 'fixed')"
    )
    await frame.click('button')
    assert await frame.evaluate("() => window.result") == 'Clicked'


@sync
async def test_click_button_devicescalefactor(isolated_page, server):
    p = isolated_page
    await p.setViewport({'width': 500, 'height': 500, 'deviceScaleFactor': 5})
    assert await p.evaluate("() => window.devicePixelRatio") == 5
    await p.setContent('<div style="width:100px;height:100px">spacer</div>')
    await attachFrame(p, server / '/input/button.html', 'button-test')
    frame = p.frames[1]
    button = await frame.J('button')
    await button.click()
    assert await frame.evaluate("() => window.result") == 'Clicked'
