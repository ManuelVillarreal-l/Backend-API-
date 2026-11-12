"""Stack (LIFO) built with linked nodes, without Python libraries.

Use in RutaSegura: undo the most recent boarding/drop-off registered on a trip.
push and pop work on the top node in O(1).
"""


class StackNode:
    def __init__(self, data, below=None):
        self.data = data
        self.below = below


class Stack:
    def __init__(self):
        self.top = None
        self.size = 0

    def push(self, item) -> None:
        self.top = StackNode(item, self.top)
        self.size += 1

    def pop(self):
        if self.top is None:
            return None
        node = self.top
        self.top = node.below
        self.size -= 1
        return node.data

    def peek(self):
        return self.top.data if self.top else None

    def is_empty(self) -> bool:
        return self.top is None

    def to_list(self) -> list:
        """Items from top to bottom."""
        out, node = [], self.top
        while node:
            out.append(node.data)
            node = node.below
        return out

    def __len__(self) -> int:
        return self.size
