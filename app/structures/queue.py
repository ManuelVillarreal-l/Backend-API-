"""Queue (FIFO). Use in RutaSegura: students waiting to board, in the order the bus will pick them up."""

from collections import deque


class Queue:
    def __init__(self): self._items = deque()
    def enqueue(self, item): self._items.append(item)
    def dequeue(self): return self._items.popleft() if self._items else None
    def peek(self): return self._items[0] if self._items else None
    def is_empty(self): return not self._items
    def to_list(self): return list(self._items)
    def __len__(self): return len(self._items)
