from syncer import sync

from tests.conftest import chrome_only


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
    assert accessibility_snapshot == expected_snapshot


@sync
async def test_report_uninteresting_nodes(isolated_page, firefox):
    def findFocusedNode(node):
        if node['focused']:
            return node
        for child in node['children']:
            focusedChild = findFocusedNode(child)
            if focusedChild:
                return focusedChild

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
    assert findFocusedNode(accessibility_snapshot) == expected_snapshot


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


class TestFilteringOfLeafNodes:
    @sync
    async def test_does_not_report_text_nodes_inside_controls(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
        <div role="tablist">
          <div role="tab" aria-selected="true"><b>Tab1</b></div>
          <div role="tab">Tab2</div>
        </div>
        """
        )
        if firefox:
            expected = {
                'role': 'document',
                'name': '',
                'children': [
                    {'role': 'pagetab', 'name': 'Tab1', 'selected': True},
                    {'role': 'pagetab', 'name': 'Tab2'},
                ],
            }
        else:
            expected = {
                'role': 'WebArea',
                'name': '',
                'children': [{'role': 'tab', 'name': 'Tab1', 'selected': True}, {'role': 'tab', 'name': 'Tab2'}],
            }
        snapshot = isolated_page.accessibility.snapshot()
        assert snapshot == expected

    @sync
    async def test_rich_editable_fields_have_children(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
            <div contenteditable="true">
                Edit this image: <img src="fakeimage.png" alt="my fake image">
            </div>
            """
        )
        if firefox:
            expected = {
                'role': 'section',
                'name': '',
                'children': [
                    {'role': 'text leaf', 'name': 'Edit this image: '},
                    {'role': 'text', 'name': 'my fake image'},
                ],
            }
        else:
            expected = {
                'role': 'generic',
                'name': '',
                'value': 'Edit this image: ',
                'children': [{'role': 'text', 'name': 'Edit this image:'}, {'role': 'img', 'name': 'my fake image'}],
            }
        snapshot = await isolated_page.accessibility.snapshot()
        assert snapshot['children'][0] == expected

    @sync
    async def test_rich_editable_fields_with_role_have_children(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
            <div contenteditable="true" role='textbox'>
                Edit this image: <img src="fakeimage.png" alt="my fake image">
            </div>
        """
        )
        if firefox:
            expected = {
                'role': 'entry',
                'name': '',
                'value': 'Edit this image: my fake image',
                'children': [{'role': 'text', 'name': 'my fake image'}],
            }
        else:
            expected = {
                'role': 'textbox',
                'name': '',
                'value': 'Edit this image: ',
                'children': [{'role': 'text', 'name': 'Edit this image:'}, {'role': 'img', 'name': 'my fake image'}],
            }
        snapshot = await isolated_page.accessibility.snapshot()
        assert snapshot['children'][0] == expected

    @chrome_only
    class TestPlainTextContentEditable:
        @sync
        async def test_field_with_role_no_children(self, isolated_page):
            await isolated_page.setContent(
                """
            <div contenteditable="plaintext-only" role='textbox'>
                Edit this image:<img src="fakeimage.png" alt="my fake image">
            </div>"""
            )
            snapshot = await isolated_page.accessibility.snapshot()
            assert snapshot['children'][0] == {'role': 'textbox', 'name': '', 'value': 'Edit this image:'}

        @sync
        async def test_field_without_role_no_content(self, isolated_page):
            await isolated_page.setContent(
                """
                <div contenteditable="plaintext-only">
                    Edit this image:<img src="fakeimage.png" alt="my fake image">
                </div>
            """
            )
            snapshot = await isolated_page.accessibility.snapshot()
            assert snapshot['children'][0] == {'role': 'generic', 'name': ''}

        @sync
        async def test_field_w_tabindex_wo_role_no_content(self, isolated_page):
            await isolated_page.setContent(
                """
                <div contenteditable="plaintext-only" tabIndex=0>
                    Edit this image:<img src="fakeimage.png" alt="my fake image">
                </div>
            """
            )
            snapshot = await isolated_page.accessibility.snapshot()
            assert snapshot['children'][0] == {'role': 'generic', 'name': ''}

    @sync
    async def test_non_editable_textbox_w_role_tabindex_label_no_children(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
        <div role="textbox" tabIndex=0 aria-checked="true" aria-label="my favorite textbox">
            this is the inner content
            <img alt="yo" src="fakeimg.png">
        </div>
        """
        )
        if firefox:
            expected = {'role': 'entry', 'name': 'my favorite textbox', 'value': 'this is the inner content yo'}
        else:
            expected = {'role': 'textbox', 'name': 'my favorite textbox', 'value': 'this is the inner content '}
        snapshot = await isolated_page.accessibility.snapshot()
        assert snapshot['children'][0] == expected

    @sync
    async def test_checkbox_with_tabindex_label_no_children(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
        <div role="checkbox" tabIndex=0 aria-checked="true" aria-label="my favorite checkbox">
          this is the inner content
          <img alt="yo" src="fakeimg.png">
        </div>
        """
        )
        if firefox:
            expected = {'role': 'checkbutton', 'name': 'my favorite checkbox', 'checked': True}
        else:
            expected = {'role': 'checkbox', 'name': 'my favorite checkbox', 'checked': True}
        snapshot = await isolated_page.accessibility.snapshot()
        assert snapshot['children'][0] == expected

    @sync
    async def test_checkbox_without_label_no_children(self, isolated_page, firefox):
        await isolated_page.setContent(
            """
        <div role="checkbox" aria-checked="true">
          this is the inner content<img alt="yo" src="fakeimg.png">
        </div>
        """
        )
        if firefox:
            expected = {'role': 'checkbutton', 'name': 'this is the inner content yo', 'checked': True}
        else:
            expected = {'role': 'checkbox', 'name': 'this is the inner content yo', 'checked': True}
        snapshot = await isolated_page.accessibility.snapshot()
        assert snapshot['children'][0] == expected

    class TestRootOption:
        @sync
        async def test_work_a_button(self, isolated_page):
            await isolated_page.setContent('<button>My Button</button>')
            button = await isolated_page.J('button')
            snapshot = isolated_page.accessibility.snapshot(root=button)
            assert snapshot == {'role': 'button', 'name': 'My Button'}

        @sync
        async def test_work_an_input(self, isolated_page):
            await isolated_page.setContent('<input title="My Input" value="My Value">')
            input_elem = await isolated_page.J('input')
            snapshot = isolated_page.accessibility.snapshot(root=input_elem)
            assert snapshot == {'role': 'textbox', 'name': 'My Input', 'value': 'My Value'}

        @sync
        async def test_work_a_menu(self, isolated_page):
            await isolated_page.setContent(
                """
            <div role="menu" title="My Menu">
              <div role="menuitem">First Item</div>
              <div role="menuitem">Second Item</div>
              <div role="menuitem">Third Item</div>
            </div>
            """
            )
            menu = await isolated_page.J('div[role="menu"]')
            snapshot = await isolated_page.accessibility.snapshot(root=menu)
            assert snapshot == {
                'role': 'menu',
                'name': 'My Menu',
                'children': [
                    {'role': 'menuitem', 'name': 'First Item'},
                    {'role': 'menuitem', 'name': 'Second Item'},
                    {'role': 'menuitem', 'name': 'Third Item'},
                ],
            }

        @sync
        async def test_return_none_when_element_no_longer_exists(self, isolated_page):
            await isolated_page.setContent('<button>My Button</button>')
            button = await isolated_page.J('button')
            await isolated_page.Jeval('button', 'b => b.remove()')
            snapshot = await isolated_page.accessibility.snapshot(root=button)
            assert snapshot is None

        @sync
        async def test_support_interesting_only(self, isolated_page):
            await isolated_page.setContent('<div><button>My Button</button></div>')
            div = await isolated_page.J('div')
            assert await isolated_page.accessibility.snapshot(root=div) is None
            assert await isolated_page.accessibility.snapshot(root=div, interestingOnly=False) == {
                'role': 'generic',
                'name': '',
                'children': [
                    {'role': 'button', 'name': 'My Button', 'children': [{'role': 'text', 'name': 'My Button'}]}
                ],
            }
