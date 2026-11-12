"""Queue (FIFO) built with linked nodes, without Python libraries.

Use in RutaSegura: students waiting to board, in the order the bus will pick them up.
enqueue adds at the tail and dequeue removes from the head, both in O(1).
"""


class QueueNode:
    def __init__(self, data):
        self.data = data
        self.next = None


class Queue:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def enqueue(self, item) -> None:
        node = QueueNode(item)
        if self.tail is None:
            self.head = self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self.size += 1

    def dequeue(self):
        if self.head is None:
            return None
        node = self.head
        self.head = node.next
        if self.head is None:
            self.tail = None
        self.size -= 1
        return node.data

    def peek(self):
        return self.head.data if self.head else None

    def is_empty(self) -> bool:
        return self.head is None

    def to_list(self) -> list:
        out, node = [], self.head
        while node:
            out.append(node.data)
            node = node.next
        return out

    def __len__(self) -> int:
        return self.size
