import platform
from collections import namedtuple

from syncer import sync

from tests.conftest import chrome_only

dimensions = """() =>
    {
      const rect = document.querySelector('textarea').getBoundingClientRect();
      return {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height
      };
    }
"""


async def evaluate_dimensions(isolated_page):
    """Execute `dimensions` script and parse value to namedTuple with x, y, width and height fields."""
    result = await isolated_page.evaluate(dimensions)
    rectTuple = namedtuple("rect", "x y width height")
    return rectTuple(x=result['x'], y=result['y'], width=result['width'], height=result['height'])


@sync
async def test_mouse_clicks_document(isolated_page):
    """It should be possible to click the document with the mouse."""
    await isolated_page.evaluate(
        """
    () => {
      window.clickPromise = new Promise(resolve => {
        document.addEventListener('click', event => {
          resolve({
            type: event.type,
            detail: event.detail,
            clientX: event.clientX,
            clientY: event.clientY,
            isTrusted: event.isTrusted,
            button: event.button
          });
        });
      });
    }
    """
    )
    await isolated_page.mouse.click(50, 60)
    event = await isolated_page.evaluate("window.clickPromise")
    assert event['type'] == 'click'
    assert event['detail'] == 1
    assert event['clientX'] == 50
    assert event['clientY'] == 60
    assert event['isTrusted']
    assert event['button'] == 0


@sync
@chrome_only
async def test_mouse_resizes_textarea(isolated_page, server):
    """It should be possible to resize the textarea with the mouse."""
    page = isolated_page
    await page.goto(server / 'input/textarea.html')
    x, y, width, height = await evaluate_dimensions(page)
    mouse = page.mouse
    await mouse.move(x + width - 4, y + height - 4)
    await mouse.down()
    await mouse.move(x + width + 100, y + height + 100)
    await mouse.up()
    newDimensions = await evaluate_dimensions(page)
    assert newDimensions.width == round(width + 104)
    assert newDimensions.height == round(height + 104)


@sync
@chrome_only
async def test_mouse_selects_text(isolated_page, server):
    """It should be possible to select the text with mouse."""
    page = isolated_page
    await page.goto(server / 'input/textarea.html')
    await page.focus('textarea')
    text = "This is the text that we are going to try to select. Let\'s see how it goes."
    await page.keyboard.type(text)
    # Firefox needs an extra frame here after typing or it will fail to set the scrollTop
    await page.evaluate("new Promise(requestAnimationFrame)")
    await page.evaluate("document.querySelector('textarea').scrollTop = 0")
    x, y, _, _ = await evaluate_dimensions(page)
    await page.mouse.move(x + 2, y + 2)
    await page.mouse.down()
    await page.mouse.move(100, 100)
    await page.mouse.up()
    result = await page.evaluate(
        """
        () => {
            const textarea = document.querySelector('textarea');
            return textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    }"""
    )
    assert result == text


@sync
@chrome_only
async def test_mouse_triggers_hover_state(isolated_page, server):
    """It should be possible to trigger hover state with the mouse."""
    page = isolated_page
    await page.goto(server / 'input/scrollable.html')
    await page.hover('#button-6')
    button6_id = await page.evaluate("document.querySelector('button:hover').id")
    assert button6_id == 'button-6'
    await page.hover('#button-2')
    button2_id = await page.evaluate("document.querySelector('button:hover').id")
    assert button2_id == 'button-2'
    await page.hover('#button-91')
    button91_id = await page.evaluate("document.querySelector('button:hover').id")
    assert button91_id == 'button-91'


@sync
@chrome_only
async def test_removing_window_node_triggers_hover(isolated_page, server):
    """It should be possible to trigger hover state with removed window.Node."""
    page = isolated_page
    await page.goto(server / 'input/scrollable.html')
    await page.evaluate("delete window.Node")
    await page.hover('#button-6')
    assert await page.evaluate("document.querySelector('button:hover').id") == 'button-6'


@sync
async def test_setting_modifier_keys_onclick(isolated_page, server, firefox):
    """It should be possible to set modifier keys on click."""
    page = isolated_page
    await page.goto(server / 'input/scrollable.html')
    await page.evaluate(
        """
            document.querySelector('#button-3').addEventListener('mousedown', e => window.lastEvent = e, true);
    """
    )
    modifiers = {'Shift': 'shiftKey', 'Control': 'ctrlKey', 'Alt': 'altKey', 'Meta': 'metaKey'}
    # In Firefox, the Meta modifier only exists on Mac
    if firefox and platform.system() != 'darwin':
        del modifiers['Meta']
    for modifier_key, modifier_value in modifiers.items():
        await page.keyboard.down(modifier_key)
        await page.click('#button-3')
        eval_modifier = await page.evaluate("mod => window.lastEvent[mod]", modifier_value)
        assert eval_modifier, f"{modifier_key, modifier_value} should be true"
        await page.keyboard.up(modifier_key)

    await page.click('#button-3')
    for modifier_key, modifier_value in modifiers.items():
        assert not await page.evaluate(
            "mod => window.lastEvent[mod]", modifier_value
        ), f"{modifier_key, modifier_value} should be false"


@sync
@chrome_only
async def test_mouse_fires_events_between_movement(isolated_page):
    """Mouse fires the events with x, y position on mouse movement."""
    page = isolated_page
    await page.mouse.move(100, 100)
    await page.evaluate(
        """() => {
      window.result = [];
      document.addEventListener('mousemove', event => {
        window.result.push([event.clientX, event.clientY]);
      });
    }"""
    )
    await page.mouse.move(200, 300, steps=5)
    assert await page.evaluate('result') == [[120, 140], [140, 180], [160, 220], [180, 260], [200, 300]]


# @see https://crbug.com/929806
@sync
@chrome_only
async def test_mobile_viewport(isolated_page, server):
    """It should be possible to work with mobile viewports and cross process navigations."""
    page = isolated_page
    await page.goto(server / "empty.html")
    await page.setViewport({'width': 360, 'height': 640, 'isMobile': True})
    await page.goto(server / 'mobile.html')
    await page.evaluate(
        """
      document.addEventListener('click', event => {
        window.result = {x: event.clientX, y: event.clientY};
      });
    """
    )
    await page.mouse.click(30, 40)
    assert await page.evaluate('result') == {'x': 30, 'y': 40}
