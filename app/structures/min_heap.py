"""Binary min-heap stored in an array, without Python libraries (replaces heapq).

Use in RutaSegura: priority queue of Dijkstra (the stop with the smallest
accumulated distance is always taken first). push and pop are O(log n).
"""


class MinHeap:
    def __init__(self):
        self.items = []

    def push(self, priority, value) -> None:
        self.items.append((priority, value))
        self._sift_up(len(self.items) - 1)

    def pop(self):
        if not self.items:
            return None
        last = len(self.items) - 1
        self.items[0], self.items[last] = self.items[last], self.items[0]
        smallest = self.items.pop()
        if self.items:
            self._sift_down(0)
        return smallest

    def _sift_up(self, i: int) -> None:
        while i > 0:
            parent = (i - 1) // 2
            if self.items[i][0] < self.items[parent][0]:
                self.items[i], self.items[parent] = self.items[parent], self.items[i]
                i = parent
            else:
                break

    def _sift_down(self, i: int) -> None:
        n = len(self.items)
        while True:
            left, right, smallest = 2 * i + 1, 2 * i + 2, i
            if left < n and self.items[left][0] < self.items[smallest][0]:
                smallest = left
            if right < n and self.items[right][0] < self.items[smallest][0]:
                smallest = right
            if smallest == i:
                return
            self.items[i], self.items[smallest] = self.items[smallest], self.items[i]
            i = smallest

    def __len__(self) -> int:
        return len(self.items)
