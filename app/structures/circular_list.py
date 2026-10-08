"""Circular list. Use in RutaSegura: daily cycle of routes that repeats every day."""

class CircularList:
    def __init__(self):
        self.items = []

    def append(self, item):
        self.items.append(item)

    def cycle(self, rounds=1):
        return self.items * rounds if self.items else []
