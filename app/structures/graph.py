"""Weighted graph (adjacency list) with Dijkstra over our own MinHeap. Use in RutaSegura: rural road network and shortest route between stops."""

from .min_heap import MinHeap

class Graph:
    def __init__(self):
        self.adj = {}

    def add_edge(self, a, b, weight=1, undirected=True):
        self.adj.setdefault(a, []).append((b, weight))
        if undirected:
            self.adj.setdefault(b, []).append((a, weight))

    def shortest_path(self, start, end):
        dist = {start: 0}
        previous = {}
        queue = MinHeap()
        queue.push(0, start)

        while queue:
            distance, node = queue.pop()
            if distance != dist.get(node):
                continue
            if node == end:
                break

            for neighbor, weight in self.adj.get(node, []):
                new_distance = distance + weight
                if new_distance < dist.get(neighbor, float("inf")):
                    dist[neighbor] = new_distance
                    previous[neighbor] = node
                    queue.push(new_distance, neighbor)

        if end not in dist:
            return [], float("inf")

        path = []
        current = end
        while current != start:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        return path, dist[end]
