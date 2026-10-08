"""N-ary tree. Use in RutaSegura: hierarchy institution -> campus -> grade -> student."""

class NaryNode:
    def __init__(self, name, data=None):
        self.name = name
        self.data = data
        self.children = []

class NaryTree:
    def __init__(self, root_name):
        self.root = NaryNode(root_name)

    def add_child(self, parent, child_name, data=None):
        node = NaryNode(child_name, data)
        parent.children.append(node)
        return node
