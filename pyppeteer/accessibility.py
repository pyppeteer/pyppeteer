from typing import TYPE_CHECKING, Dict, List, Set, Union

if TYPE_CHECKING:
    from pyppeteer.connection.cdpsession import CDPSession
    from pyppeteer.jshandle import ElementHandle


class Accessibility:
    def __init__(self, client: 'CDPSession'):
        self._client = client

    async def snapshot(self, interestingOnly: bool = True, root: 'ElementHandle' = None):
        nodes = (await self._client.send('Accessibility.getFullAXTree'))['nodes']
        backendNodeId = None
        if root:
            node = (await self._client.send('DOM.describeNode', {'objectId': root._remoteObject['objectId']}))['node']
            backendNodeId = node['backendNodeId']
        defaultRoot = AXNode.createTree(nodes)
        needle = defaultRoot
        if backendNodeId:
            needle = defaultRoot.find(lambda _node: _node._payload['backendDOMNodeId'] == backendNodeId)
            if not needle:
                return
        if not interestingOnly:
            return serializeTree(needle)[0]

        interestingNodes = set()
        collectInterestingNodes(interestingNodes, defaultRoot, False)
        if needle not in interestingNodes:
            return None
        return serializeTree(needle, interestingNodes)[0]


class AXNode:
    def __init__(self, payload: Dict):
        """
        :param payload: dict with keys nodeId, name, role, properties
        """
        self._payload = payload
        self._children: List[AXNode] = []
        self._richlyEditable = False
        self._editable = False
        self._focusable = False
        self._expanded = False
        self._hidden = False
        self._name = payload.get('name', {}).get('value', '')
        self._role = payload.get('role', {}).get('value', 'Unknown')
        self._cacheHasFocusableChild = None

        for property in payload.get('properties', []):
            _name = property['name']
            _value = property.get('value', {}).get('value', None)
            if _name == 'editable':
                self._richlyEditable = _value == 'richtext'
                self._editable = True
            if _name == 'focusable':
                self._focusable = _value
            if _name == 'expanded':
                self._expanded = _value
            if _name == 'hidden':
                self._hidden = _value

    @property
    def _isPlainTextField(self):
        if self._richlyEditable:
            return False
        if self._editable:
            return True
        return self._role in ['textbox', 'ComboBox', 'searchbox']

    @property
    def _isTextOnlyObject(self):
        return self._role in ['LineBreak', 'text', 'InlineTextBox']

    @property
    def _hasFocusableChild(self):
        if self._cacheHasFocusableChild is None:
            self._cacheHasFocusableChild = False
            for child in self._children:
                if child._focusable or child._hasFocusableChild:
                    self._cacheHasFocusableChild = True
                    break
        return self._cacheHasFocusableChild

    def find(self, predicate):
        if predicate(self):
            return self
        for child in self._children:
            result = child.find(predicate)
            if result:
                return result

    def isLeafNode(self):
        if not self._children:
            return True

        # These types of objects may have children that we use as internal
        # implementation details, but we want to expose them as leaves to platform
        # accessibility APIs because screen readers might be confused if they find
        # any children.
        if self._isPlainTextField or self._isTextOnlyObject:
            return True
        # Roles whose children are only presentational according to the ARIA and
        # HTML5 Specs should be hidden from screen readers.
        # (Note that whilst ARIA buttons can have only presentational children, HTML5
        # buttons are allowed to have content.)
        if self._role in [
            'doc-cover',
            'graphics-symbol',
            'img',
            'Meter',
            'scrollbar',
            'slider',
            'separator',
            'progressbar',
        ]:
            return True

        # here and below: android heuristics
        if self._hasFocusableChild:
            return False
        if self._focusable and self._name:
            return True
        if self._role == 'heading' and self._name:
            return True
        return False

    @property
    def isControl(self):
        return self._role in [
            'button',
            'checkbox',
            'ColorWell',
            'combobox',
            'DisclosureTriangle',
            'listbox',
            'menu',
            'menubar',
            'menuitem',
            'menuitemcheckbox',
            'menuitemradio',
            'radio',
            'scrollbar',
            'searchbox',
            'slider',
            'spinbutton',
            'switch',
            'tab',
            'textbox',
            'tree',
        ]

    def isInteresting(self, insideControl: bool) -> bool:
        role = self._role
        if role == 'Ignored' or self._hidden:
            return False
        if self._focusable or self._richlyEditable:
            return True

        # If it's not focusable but has a control role, then it's interesting.
        if self.isControl:
            return True

        # A non focusable child of a control is not interesting
        if insideControl:
            return False
        return self.isLeafNode() and bool(self._name)

    def serialize(self):  # noqa C901
        properties: Dict[str, Union[str, float, bool]] = {}
        for property_ in self._payload.get('properties', []):
            properties[property_['name'].lower()] = property_['value'].get('value')
        if self._payload.get('name'):
            properties['name'] = self._payload['name']['value']
        if self._payload.get('value'):
            properties['value'] = self._payload['value']['value']
        if self._payload.get('description'):
            properties['description'] = self._payload['description']['value']

        node = {'role': self._role}
        userStringProperties = [
            'name',
            'value',
            'description',
            'keyshortcuts',
            'roledescription',
            'valuetext',
        ]
        for prop in userStringProperties:
            if prop not in properties:
                continue
            node[prop] = properties[prop]
        booleanProperties = [
            'disabled',
            'expanded',
            'focused',
            'modal',
            'multiline',
            'multiselectable',
            'readonly',
            'required',
            'selected',
        ]
        for prop in booleanProperties:
            # WebArea's treat focus differently than other nodes. They report whether their frame  has focus,
            # not whether focus is specifically on the root node.
            if prop == 'focused' and self._role == 'WebArea':
                continue
            value = properties.get(prop)
            if value:
                node[prop] = value

        tristateProperties = [
            'checked',
            'pressed',
        ]
        for prop in tristateProperties:
            if prop not in properties:
                continue
            value = properties.get(prop)
            if value != 'mixed':
                if value == 'true':
                    value = True
                else:
                    value = False
            node[prop] = value

        numericProperties = [
            'level',
            'valuemax',
            'valuemin',
        ]
        for prop in numericProperties:
            if prop not in properties:
                continue
            node[prop] = properties.get(prop)

        tokenProperties = [
            'autocomplete',
            'haspopup',
            'invalid',
            'orientation',
        ]
        for prop in tokenProperties:
            value = properties.get(prop)
            if not value or value == 'false':
                continue
            node[prop] = value
        return node

    @staticmethod
    def createTree(payloads: List[dict]) -> 'AXNode':
        """

        :param payloads: List of dictionaries of AXNode kwargs
        :return:
        """
        nodeById = {}
        for payload in payloads:
            nodeById[payload['nodeId']] = AXNode(payload)
        for node in nodeById.values():
            for childId in node._payload.get('childIds', []):
                node._children.append(nodeById[childId])
        return [*nodeById.values()][0]


def collectInterestingNodes(collection: Set[AXNode], node: AXNode, insideControl: bool):
    if node.isInteresting(insideControl):
        collection.add(node)
    if node.isLeafNode():
        return
    insideControl = insideControl or node.isControl
    for child in node._children:
        collectInterestingNodes(collection, child, insideControl)


def serializeTree(node: 'AXNode', whitelistedNodes: Set[AXNode] = None):
    children = []
    for child in node._children:
        children.extend(serializeTree(child, whitelistedNodes))
    if whitelistedNodes and node not in whitelistedNodes:
        return children
    serializedNode = node.serialize()
    if children:
        serializedNode['children'] = children
    return [serializedNode]
