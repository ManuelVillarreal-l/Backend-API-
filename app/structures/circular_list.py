"""Circular singly linked list (real nodes: the last node points back to the first).

Use in RutaSegura: weekly duty rotation of route monitors. After the last monitor,
the rotation starts again with the first one, forever.
"""


class CNode:
    def __init__(self, data):
        self.data = data
        self.next = None


class CircularList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def append(self, data) -> None:
        node = CNode(data)
        if self.head is None:
            self.head = self.tail = node
            node.next = node
        else:
            node.next = self.head
            self.tail.next = node
            self.tail = node
        self.size += 1

    def cycle(self, steps: int, start_index: int = 0) -> list:
        """Walk the circle `steps` times starting at position `start_index`."""
        if self.head is None or steps <= 0:
            return []
        node = self.head
        for _ in range(start_index % self.size):
            node = node.next
        out = []
        for _ in range(steps):
            out.append(node.data)
            node = node.next
        return out

    def to_list(self) -> list:
        return self.cycle(self.size)

    def __len__(self) -> int:
        return self.size
