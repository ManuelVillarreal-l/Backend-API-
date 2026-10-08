"""Doubly linked list. Use in RutaSegura: traverse a route forward (outbound) and backward (return)."""

class DNode:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None

class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None

    def append(self, data):
        node = DNode(data)
        if not self.head:
            self.head = self.tail = node
            return
        node.prev = self.tail
        self.tail.next = node
        self.tail = node

    def forward(self):
        out, cur = [], self.head
        while cur:
            out.append(cur.data)
            cur = cur.next
        return out

    def backward(self):
        out, cur = [], self.tail
        while cur:
            out.append(cur.data)
            cur = cur.prev
        return out
