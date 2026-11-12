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
        self.size = 0

    def insert(self, key, value=None):
        def rec(node):
            if not node:
                self.size += 1
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

    def delete(self, key) -> bool:
        """Remove a key. Three cases: leaf, one child, or two children (use the in-order successor)."""
        removed = False

        def rec(node, key):
            nonlocal removed
            if not node:
                return None
            if key < node.key:
                node.left = rec(node.left, key)
            elif key > node.key:
                node.right = rec(node.right, key)
            else:
                removed = True
                if not node.left:
                    return node.right
                if not node.right:
                    return node.left
                successor = node.right
                while successor.left:
                    successor = successor.left
                node.key, node.value = successor.key, successor.value
                node.right = rec(node.right, successor.key)
            return node

        self.root = rec(self.root, key)
        if removed:
            self.size -= 1
        return removed

    def in_order(self) -> list:
        out = []

        def rec(node):
            if node:
                rec(node.left)
                out.append(node.key)
                rec(node.right)

        rec(self.root)
        return out

    def height(self) -> int:
        def rec(node):
            return 0 if not node else 1 + max(rec(node.left), rec(node.right))

        return rec(self.root)
