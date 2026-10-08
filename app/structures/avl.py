"""AVL tree (self-balancing BST). Use in RutaSegura: balanced student index with O(log n) search."""

class AVLNode:
    def __init__(self, key, value=None):
        self.key, self.value = key, value
        self.left = None
        self.right = None
        self.height = 1

class AVLTree:
    def __init__(self):
        self.root = None

    def height(self, node):
        return node.height if node else 0

    def update(self, node):
        node.height = 1 + max(self.height(node.left), self.height(node.right))

    def rotate_right(self, y):
        x = y.left
        t = x.right
        x.right = y
        y.left = t
        self.update(y)
        self.update(x)
        return x

    def rotate_left(self, x):
        y = x.right
        t = y.left
        y.left = x
        x.right = t
        self.update(x)
        self.update(y)
        return y

    def balance(self, node):
        return self.height(node.left) - self.height(node.right) if node else 0

    def insert(self, key, value=None):
        def rec(node):
            if not node:
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





