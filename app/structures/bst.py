"""Binary search tree.

Use in RutaSegura: index of the students of a trip by QR code, so each scan
finds the student in O(log n) on average instead of checking the whole list.
"""


class BSTNode:
    def __init__(self, key, value=None):
        self.key, self.value = key, value
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None

    def insert(self, key, value=None):
        def rec(node):
            if not node:
                return BSTNode(key, value)
            if key < node.key:
                node.left = rec(node.left)
            elif key > node.key:
                node.right = rec(node.right)
            else:
                node.value = value
            return node

        self.root = rec(self.root)

    def search(self, key):
        node = self.root
        while node:
            if key == node.key:
                return node.value
            node = node.left if key < node.key else node.right
        return None
