from collections import Set
from typing import List

from pyppeteer.element_handle import ElementHandle


class Accessibility(object):
    def __init__(self, client):
        self._client = client

    async def snapshot(self, interstingOnly: bool = None, root: ElementHandle = None):
        nodes = await self._client.send('Accessibility.getFullAXTree')
        backendNodeId = None
        if root:
            node = await self._client.send(
                'DOM.describeNode', {
                    'objectId': 'root._remoteObject.objectId',
                }
            )
            backendNodeId = node['backendNodeId']
        defaultRoot = AXNode.createTree(nodes)
        needle = defaultRoot
        if backendNodeId:
            needle = [
                node for node in defaultRoot
                if node._payload.backendDOMNodeId == backendNodeId
            ]
            if not needle:
                return
            needle = needle[0]
        if not interstingOnly:
            return serializeTree(needle)[0]

        interestingNodes = set()
        collectInterstingNodes(interestingNodes, defaultRoot, False)
        if needle not in interestingNodes:
            return None
        return serializeTree(needle, interestingNodes)[0]


class AXNode(object):
    def __init__(self, payload: 'AXNode'):
        self._payload = payload

    def _isPlainTextField(self):
        pass

    def _isTextOnlyObject(self):
        pass

    def _hasFocusableChild(self):
        pass

    def find(self, predicate):
        pass

    def isLeafNode(self):
        pass

    def isControl(self):
        pass

    def isInteresting(self, insideControl: bool):
        pass

    def serialize(self):
        pass

    @staticmethod
    def createTree(payloads: List['AXNode']):
        pass


def collectInterstingNodes(
        collection: Set[AXNode],
        node: AXNode,
        insideControl: bool
):
    if node.isInteresting(insideControl):
        collection.add(node)
    if node.isLeafNode():
        return
    insideControl = insideControl or node.isControl()
    for child in node._children:
        collectInterstingNodes(collection, child, insideControl)


def serializeTree(node: 'AXNode', whitelistedNodes: Set[AXNode] = None):
    children = []
    for child in node._children:
        children.append(serializeTree(child, whitelistedNodes))
    if whitelistedNodes and node not in whitelistedNodes:
        return children
    serializedNode = node.serialize()
    if children:
        serializedNode.children = children
    return [serializedNode]
