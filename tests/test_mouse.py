from asyncio import gather
from collections import namedtuple

from tests.conftest import chrome_only

import pytest
from syncer import sync


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
async def test_click_document(isolated_page):
    """should click the document"""
    await isolated_page.evaluate("""
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
    """)
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
async def test_resize_textarea(isolated_page, server):
    """should resize the textarea"""
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
async def test_select_text_with_mouse(isolated_page, server):
    """should select the text with mouse"""
    page = isolated_page
    await page.goto(server / 'input/textarea.html')
    await page.focus('textarea')
    text = "This is the text that we are going to try to select. Let\'s see how it goes."
    await page.keyboard.type(text)
    # Firefox needs an extra frame here after typing or it will fail to set the scrollTop
    await page.evaluate("() => new Promise(requestAnimationFrame)")
    await page.evaluate("() => document.querySelector('textarea').scrollTop = 0")
    x, y, _, _ = await evaluate_dimensions(page)
    await page.mouse.move(x + 2, y + 2)
    await page.mouse.down()
    await page.mouse.move(100,100)
    await page.mouse.up()
    result = await page.evaluate("""
        () => {
            const textarea = document.querySelector('textarea');
            return textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    }""")
    assert result == text


@sync
@chrome_only
async def test_trigger_hover_state():
    """should trigger hover state"""
    # const { page, server } = getTestState();
    #
    # await page.goto(server.PREFIX + '/input/scrollable.html');
    # await page.hover('#button-6');
    # expect(await page.evaluate(() => document.querySelector('button:hover').id)).toBe('button-6');
    # await page.hover('#button-2');
    # expect(await page.evaluate(() => document.querySelector('button:hover').id)).toBe('button-2');
    # await page.hover('#button-91');
    # expect(await page.evaluate(() => document.querySelector('button:hover').id)).toBe('button-91');

@chrome_only
def test_trigger_hover_removed_window_node():
    """should trigger hover state with removed window.Node"""
    # const { page, server } = getTestState();
    #
    # await page.goto(server.PREFIX + '/input/scrollable.html');
    # await page.evaluate(() => delete window.Node);
    # await page.hover('#button-6');
    # expect(await page.evaluate(() => document.querySelector('button:hover').id)).toBe('button-6');


def test_set_modifier_keys_onclick():
    """should set modifier keys on click"""
    # const { page, server, isFirefox } = getTestState();
    #
    # await page.goto(server.PREFIX + '/input/scrollable.html');
    # await page.evaluate(() => document.querySelector('#button-3').addEventListener('mousedown', e => window.lastEvent = e, true));
    # const modifiers = {'Shift': 'shiftKey', 'Control': 'ctrlKey', 'Alt': 'altKey', 'Meta': 'metaKey'};
    # // In Firefox, the Meta modifier only exists on Mac
    # if (isFirefox && os.platform() !== 'darwin')
    #   delete modifiers['Meta'];
    # for (const modifier in modifiers) {
    #   await page.keyboard.down(modifier);
    #   await page.click('#button-3');
    #   if (!(await page.evaluate(mod => window.lastEvent[mod], modifiers[modifier])))
    #     throw new Error(modifiers[modifier] + ' should be true');
    #   await page.keyboard.up(modifier);
    # }
    # await page.click('#button-3');
    # for (const modifier in modifiers) {
    #   if ((await page.evaluate(mod => window.lastEvent[mod], modifiers[modifier])))
    #     throw new Error(modifiers[modifier] + ' should be false');


@chrome_only
def test_tween_mouse_movement():
    """should tween mouse movement"""
    # const { page } = getTestState();
    #
    # await page.mouse.move(100, 100);
    # await page.evaluate(() => {
    #   window.result = [];
    #   document.addEventListener('mousemove', event => {
    #     window.result.push([event.clientX, event.clientY]);
    #   });
    # });
    # await page.mouse.move(200, 300, {steps: 5});
    # expect(await page.evaluate('result')).toEqual([
    #   [120, 140],
    #   [140, 180],
    #   [160, 220],
    #   [180, 260],
    #   [200, 300]
    # ]);


# @see https://crbug.com/929806
@chrome_only
def test_mobile_viewport():
    """should work with mobile viewports and cross process navigations"""
    # const { page, server } = getTestState();
    #
    # await page.goto(server.EMPTY_PAGE);
    # await page.setViewport({width: 360, height: 640, isMobile: true});
    # await page.goto(server.CROSS_PROCESS_PREFIX + '/mobile.html');
    # await page.evaluate(() => {
    #   document.addEventListener('click', event => {
    #     window.result = {x: event.clientX, y: event.clientY};
    #   });
    # });
    #
    # await page.mouse.click(30, 40);
    #
    # expect(await page.evaluate('result')).toEqual({x: 30, y: 40});
