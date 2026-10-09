"""AVL tree (self-balancing binary search tree).

Use in RutaSegura: index of students by name for fast search as the coordinator types.
Insertion and exact search are O(log n); a prefix search visits only the branches
that can contain matches.
"""


class AVLNode:
    def __init__(self, key, value=None):
        self.key, self.value = key, value
        self.left = None
        self.right = None
        self.height = 1


class AVLTree:
    def __init__(self):
        self.root = None
        self.size = 0

    def height(self, node):
        return node.height if node else 0

    def update(self, node):
        node.height = 1 + max(self.height(node.left), self.height(node.right))

    def balance(self, node):
        return self.height(node.left) - self.height(node.right) if node else 0

    def rotate_right(self, y):
        x = y.left
        y.left = x.right
        x.right = y
        self.update(y)
        self.update(x)
        return x

    def rotate_left(self, x):
        y = x.right
        x.right = y.left
        y.left = x
        self.update(x)
        self.update(y)
        return y

    def insert(self, key, value=None):
        def rec(node):
            if not node:
                self.size += 1
                return AVLNode(key, value)
            if key < node.key:
                node.left = rec(node.left)
            elif key > node.key:
                node.right = rec(node.right)
            else:
                node.value = value
                return node

            self.update(node)
            balance = self.balance(node)
            if balance > 1 and key < node.left.key:
                return self.rotate_right(node)
            if balance < -1 and key > node.right.key:
                return self.rotate_left(node)
            if balance > 1 and key > node.left.key:
                node.left = self.rotate_left(node.left)
                return self.rotate_right(node)
            if balance < -1 and key < node.right.key:
                node.right = self.rotate_right(node.right)
                return self.rotate_left(node)
            return node

        self.root = rec(self.root)

    def search(self, key):
        node = self.root
        while node:
            if key == node.key:
                return node.value
            node = node.left if key < node.key else node.right
        return None

    def prefix_search(self, prefix: str, limit: int = 20) -> list:
        """Values whose key (a string or a tuple starting with a string) starts with prefix."""
        out = []

        def key_text(key):
            return key[0] if isinstance(key, tuple) else key

        def rec(node):
            if not node or len(out) >= limit:
                return
            text = key_text(node.key)
            if prefix <= text:
                rec(node.left)
            if text.startswith(prefix) and len(out) < limit:
                out.append(node.value)
            if text < prefix or text.startswith(prefix):
                rec(node.right)

        rec(self.root)
        return out

    def in_order(self) -> list:
        out = []

        def rec(node):
            if node:
                rec(node.left)
                out.append(node.key)
                rec(node.right)

        rec(self.root)
        return out
