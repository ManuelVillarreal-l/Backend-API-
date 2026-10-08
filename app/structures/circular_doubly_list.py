"""Circular doubly linked list. Use in RutaSegura: rotation of drivers between shifts."""

class CircularDoublyList:
    def __init__(self):
        self.items = []
        self.index = 0

    def append(self, item):
        self.items.append(item)

    def next(self):
        if not self.items:
            return None
        value = self.items[self.index]
        self.index = (self.index + 1) % len(self.items)
        return value
