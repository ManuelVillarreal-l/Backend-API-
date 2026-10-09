"""N-ary tree (each node can have any number of children).

Use in RutaSegura: hierarchy school -> campus -> grade -> students.
"""


class NaryNode:
    def __init__(self, name, data=None):
        self.name = name
        self.data = data
        self.children = []


class NaryTree:
    def __init__(self, root_name, data=None):
        self.root = NaryNode(root_name, data)

    def add_child(self, parent, child_name, data=None):
        node = NaryNode(child_name, data)
        parent.children.append(node)
        return node

    def find_child(self, parent, child_name):
        for child in parent.children:
            if child.name == child_name:
                return child
        return None

    def count_leaves(self, node=None) -> int:
        node = node or self.root
        if not node.children:
            return 1
        return sum(self.count_leaves(child) for child in node.children)

    def to_dict(self, node=None) -> dict:
        node = node or self.root
        return {
            "name": node.name,
            "data": node.data,
            "children": [self.to_dict(child) for child in node.children],
        }
