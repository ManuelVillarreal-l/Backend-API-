"""Circular doubly linked list (real nodes with next and prev, closed in a ring).

Use in RutaSegura: driver shift rotation. From any driver you can move to the
next or the previous one; after the last comes the first and vice versa.
"""


class CDNode:
    def __init__(self, data):
        self.data = data
        self.next = None
        self.prev = None


class CircularDoublyList:
    def __init__(self):
        self.head = None
        self.size = 0
        self.current = None

    def append(self, data) -> None:
        node = CDNode(data)
        if self.head is None:
            node.next = node.prev = node
            self.head = self.current = node
        else:
            tail = self.head.prev
            tail.next = node
            node.prev = tail
            node.next = self.head
            self.head.prev = node
        self.size += 1

    def find(self, predicate):
        """Move `current` to the first node whose data satisfies predicate."""
        node = self.head
        for _ in range(self.size):
            if predicate(node.data):
                self.current = node
                return node.data
            node = node.next
        return None

    def next(self):
        if self.current is None:
            return None
        self.current = self.current.next
        return self.current.data

    def prev(self):
        if self.current is None:
            return None
        self.current = self.current.prev
        return self.current.data

    def to_list(self) -> list:
        out, node = [], self.head
        for _ in range(self.size):
            out.append(node.data)
            node = node.next
        return out

    def __len__(self) -> int:
        return self.size
