"""Singly linked list.

Use in RutaSegura: ordered sequence of the stops of a route. The ETA walks the
list from the next stop up to the stop the guardian is waiting at.
"""


class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


class LinkedList:
    def __init__(self):
        self.head = None
        self.tail = None

    def append(self, data):
        node = Node(data)
        if not self.head:
            self.head = self.tail = node
        else:
            self.tail.next = node
            self.tail = node

    def find_node(self, predicate):
        node = self.head
        while node:
            if predicate(node.data):
                return node
            node = node.next
        return None

    def to_list(self):
        out, cur = [], self.head
        while cur:
            out.append(cur.data)
            cur = cur.next
        return out
