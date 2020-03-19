from syncer import sync


@sync
async def test_accessibility_properties(shared_browser, isolated_page, firefox):
    await isolated_page.setContent(
        """
    <head>
        <title>Accessibility Test</title>
      </head>
      <body>
        <div>Hello World</div>
        <h1>Inputs</h1>
        <input placeholder="Empty input" autofocus />
        <input placeholder="readonly input" readonly />
        <input placeholder="disabled input" disabled />
        <input aria-label="Input with whitespace" value="  " />
        <input value="value only" />
        <input aria-placeholder="placeholder" value="and a value" />
        <div aria-hidden="true" id="desc">This is a description!</div>
        <input aria-placeholder="placeholder" value="and a value" aria-describedby="desc" />
        <select>
          <option>First Option</option>
          <option>Second Option</option>
        </select>
      </body>`
    """
    )
    await isolated_page.focus('[placeholder="Empty input"]')
    accessibility_snapshot = await isolated_page.accessibility.snapshot()
    if firefox:
        expected_snapshot = {
            'role': 'document',
            'name': 'Accessibility Test',
            'children': [
                {'role': 'text leaf', 'name': 'Hello World'},
                {'role': 'heading', 'name': 'Inputs', 'level': 1},
                {'role': 'entry', 'name': 'Empty input', 'focused': True},
                {'role': 'entry', 'name': 'readonly input', 'readonly': True},
                {'role': 'entry', 'name': 'disabled input', 'disabled': True},
                {'role': 'entry', 'name': 'Input with whitespace', 'value': '  '},
                {'role': 'entry', 'name': '', 'value': 'value only'},
                {'role': 'entry', 'name': '', 'value': 'and a value'},
                {'role': 'entry', 'name': '', 'value': 'and a value', 'description': 'This is a description!'},
                {
                    'role': 'combobox',
                    'name': '',
                    'value': 'First Option',
                    'haspopup': True,
                    'children': [
                        {'role': 'combobox option', 'name': 'First Option', 'selected': True},
                        {'role': 'combobox option', 'name': 'Second Option'},
                    ],
                },
            ],
        }
    else:
        expected_snapshot = {
            'role': 'WebArea',
            'name': 'Accessibility Test',
            'children': [
                {'role': 'text', 'name': 'Hello World'},
                {'role': 'heading', 'name': 'Inputs', 'level': 1},
                {'role': 'textbox', 'name': 'Empty input', 'focused': True},
                {'role': 'textbox', 'name': 'readonly input', 'readonly': True},
                {'role': 'textbox', 'name': 'disabled input', 'disabled': True},
                {'role': 'textbox', 'name': 'Input with whitespace', 'value': '  '},
                {'role': 'textbox', 'name': '', 'value': 'value only'},
                {'role': 'textbox', 'name': 'placeholder', 'value': 'and a value'},
                {
                    'role': 'textbox',
                    'name': 'placeholder',
                    'value': 'and a value',
                    'description': 'This is a description!',
                },
                {
                    'role': 'combobox',
                    'name': '',
                    'value': 'First Option',
                    'children': [
                        {'role': 'menuitem', 'name': 'First Option', 'selected': True},
                        {'role': 'menuitem', 'name': 'Second Option'},
                    ],
                },
            ],
        }
    assert expected_snapshot == accessibility_snapshot


@sync
async def test_report_uninteresting_nodes(isolated_page, firefox):
    await isolated_page.setContent('<textarea>Hi</textarea>')
    await isolated_page.focus('textarea')
    accessibility_snapshot = await isolated_page.accessibility.snapshot(interestingOnly=False)
    if firefox:
        expected_snapshot = {
            'role': 'entry',
            'name': '',
            'value': 'hi',
            'focused': True,
            'multiline': True,
            'children': [{'role': 'text leaf', 'name': 'hi'}],
        }
    else:
        expected_snapshot = {
            'role': 'textbox',
            'name': '',
            'value': 'hi',
            'focused': True,
            'multiline': True,
            'children': [{'role': 'generic', 'name': '', 'children': [{'role': 'text', 'name': 'hi'}]}],
        }
    assert accessibility_snapshot == expected_snapshot

@sync
async def test_roled_description(isolated_page):
    await isolated_page.setContent('<div tabIndex=-1 aria-roledescription="foo">Hi</div>')
    snapshot = await isolated_page.accessibility.snapshot()
    assert snapshot['children'][0]['roledescription'] == 'foo'

@sync
async def test_orientation(isolated_page):
    await isolated_page.setContent('<a href="" role="slider" aria-orientation="vertical">11</a>')
    snapshot = await isolated_page.accessibility.snapshot()
    assert snapshot['children'][0]['orientation'] == 'vertical'

@sync
async def test_autocomplete(isolated_page):
    await isolated_page.setContent('<input type="number" aria-autocomplete="list" />')
    snapshot = await isolated_page.accessibility.snapshot()
    assert snapshot['children'][0]['autocomplete'] == 'list'

@sync
async def test_multiselectable(isolated_page):
    await isolated_page.setContent('<div role="grid" tabIndex=-1 aria-multiselectable=true>hey</div>')
    snapshot = await isolated_page.accessibility.snapshot()
    assert snapshot['children'][0]['multiselectable']

@sync
async def test_keyshortcuts(isolated_page):
    await isolated_page.setContent('<div role="grid" tabIndex=-1 aria-keyshortcuts="foo">hey</div>')
    snapshot = await isolated_page.accessibility.snapshot()
    assert snapshot['children'][0]['keyshortcuts'] == 'foo'