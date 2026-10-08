"""Stack (LIFO). Use in RutaSegura: undo the latest changes made to a route."""

class Stack:
    def __init__(self): self._items = []
    def push(self, item): self._items.append(item)
    def pop(self): return self._items.pop() if self._items else None
    def peek(self): return self._items[-1] if self._items else None
    def is_empty(self): return not self._items
    def __len__(self): return len(self._items)
