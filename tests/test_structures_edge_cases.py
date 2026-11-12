"""Edge cases of the data structures: empty structures, one element and limits.

These tests complement tests/test_structures.py and do not need the API or the database.
"""

from app.structures.avl import AVLTree
from app.structures.bst import BST
from app.structures.circular_doubly_list import CircularDoublyList
from app.structures.circular_list import CircularList
from app.structures.doubly_linked_list import DoublyLinkedList
from app.structures.graph import Graph
from app.structures.linked_list import LinkedList
from app.structures.min_heap import MinHeap
from app.structures.queue import Queue
from app.structures.stack import Stack


# --- Circular list (monitor rotation) ---------------------------------------------

def test_circular_list_empty():
    rotation = CircularList()
    assert len(rotation) == 0
    assert rotation.to_list() == []
    assert rotation.cycle(5) == []


def test_circular_list_single_node_points_to_itself():
    rotation = CircularList()
    rotation.append("Monitora A")
    assert rotation.head.next is rotation.head
    assert rotation.cycle(3) == ["Monitora A"] * 3


def test_circular_list_last_node_closes_the_ring():
    rotation = CircularList()
    for name in ("A", "B", "C"):
        rotation.append(name)
    assert rotation.tail.next is rotation.head
    assert rotation.cycle(7) == ["A", "B", "C", "A", "B", "C", "A"]


def test_circular_list_start_index_wraps_around():
    rotation = CircularList()
    for name in ("A", "B", "C"):
        rotation.append(name)
    # Starting at index 4 is the same as starting at index 1 (4 % 3).
    assert rotation.cycle(3, start_index=4) == ["B", "C", "A"]
    assert rotation.cycle(0) == []


# --- Circular doubly linked list (driver rotation) --------------------------------

def test_circular_doubly_list_empty_has_no_current():
    drivers = CircularDoublyList()
    assert drivers.next() is None
    assert drivers.prev() is None
    assert drivers.find(lambda d: True) is None
    assert drivers.to_list() == []


def test_circular_doubly_list_single_node():
    drivers = CircularDoublyList()
    drivers.append("Conductor 1")
    assert drivers.next() == "Conductor 1"
    assert drivers.prev() == "Conductor 1"


def test_circular_doubly_list_wraps_in_both_directions():
    drivers = CircularDoublyList()
    for name in ("D1", "D2", "D3"):
        drivers.append(name)
    assert drivers.head.prev.data == "D3"
    assert drivers.find(lambda d: d == "D3") == "D3"
    assert drivers.next() == "D1"  # after the last comes the first
    assert drivers.prev() == "D3"  # and before the first comes the last
    assert drivers.find(lambda d: d == "D9") is None


# --- Singly linked list (stops of a route) ----------------------------------------

def test_linked_list_empty():
    stops = LinkedList()
    assert stops.to_list() == []
    assert stops.find_node(lambda s: True) is None


def test_linked_list_keeps_insertion_order_and_tail():
    stops = LinkedList()
    for name in ("Vereda El Encano", "Vereda Santa Lucía", "Institución Educativa"):
        stops.append(name)
    assert stops.to_list()[0] == "Vereda El Encano"
    assert stops.tail.data == "Institución Educativa"
    assert stops.tail.next is None
    node = stops.find_node(lambda s: s.startswith("Vereda S"))
    assert node.next.data == "Institución Educativa"


# --- Doubly linked list (outbound and return itinerary) ---------------------------

def test_doubly_linked_list_empty():
    route = DoublyLinkedList()
    assert route.forward() == []
    assert route.backward() == []


def test_doubly_linked_list_single_node_is_head_and_tail():
    route = DoublyLinkedList()
    route.append("Escuela")
    assert route.head is route.tail
    assert route.forward() == route.backward() == ["Escuela"]


def test_doubly_linked_list_return_is_outbound_reversed():
    route = DoublyLinkedList()
    for stop in ("P1", "P2", "P3", "P4"):
        route.append(stop)
    assert route.backward() == list(reversed(route.forward()))
    assert route.head.prev is None and route.tail.next is None


# --- Queue (boarding order) and stack (undo) ---------------------------------------

def test_queue_empty_returns_none():
    boarding = Queue()
    assert boarding.is_empty()
    assert boarding.dequeue() is None
    assert boarding.peek() is None
    assert len(boarding) == 0


def test_queue_can_be_reused_after_emptying():
    boarding = Queue()
    boarding.enqueue("Juan")
    assert boarding.dequeue() == "Juan"
    assert boarding.head is None and boarding.tail is None
    boarding.enqueue("Valentina")
    boarding.enqueue("Mateo")
    assert boarding.to_list() == ["Valentina", "Mateo"]
    assert boarding.peek() == "Valentina"


def test_stack_empty_returns_none():
    undo = Stack()
    assert undo.is_empty()
    assert undo.pop() is None
    assert undo.peek() is None


def test_stack_undo_reverses_the_order_of_events():
    undo = Stack()
    events = ["abordó Juan", "abordó Valentina", "bajó Juan"]
    for event in events:
        undo.push(event)
    undone = [undo.pop() for _ in range(len(events))]
    assert undone == list(reversed(events))
    assert undo.is_empty() and len(undo) == 0


# --- BST (QR lookup) and AVL (search by name) -------------------------------------

def test_bst_empty_and_missing_keys():
    index = BST()
    assert index.search("RS-0001") is None
    assert index.delete("RS-0001") is False
    assert index.height() == 0


def test_bst_duplicate_key_updates_value_without_growing():
    index = BST()
    index.insert("RS-0001", "Juan")
    index.insert("RS-0001", "Juan Pérez")
    assert index.size == 1
    assert index.search("RS-0001") == "Juan Pérez"


def test_bst_sorted_inserts_degrade_but_avl_does_not():
    """Why the project also needs an AVL: sorted inserts turn a BST into a list."""
    bst, avl = BST(), AVLTree()
    for n in range(1, 64):
        bst.insert(n)
        avl.insert(n)
    assert bst.height() == 63
    assert avl.height(avl.root) <= 7  # log2(64) = 6, AVL height <= 1.44 log2(n)
    assert avl.in_order() == list(range(1, 64))


def test_avl_prefix_search_empty_and_limit():
    names = AVLTree()
    assert names.prefix_search("ju") == []
    for i in range(30):
        names.insert(f"juan {i:02d}", i)
    assert len(names.prefix_search("juan", limit=5)) == 5
    assert names.prefix_search("zz") == []


# --- Min-heap and graph (shortest path between stops) -----------------------------

def test_min_heap_empty_and_heap_sort():
    heap = MinHeap()
    assert heap.pop() is None
    for priority in (7, 3, 9, 1, 5, 3):
        heap.push(priority, f"p{priority}")
    assert [heap.pop()[0] for _ in range(6)] == [1, 3, 3, 5, 7, 9]
    assert len(heap) == 0


def test_graph_unreachable_stop():
    roads = Graph()
    roads.add_edge("Escuela", "El Encano", 4)
    roads.add_edge("La Laguna", "Santa Lucía", 2)  # another component
    path, distance = roads.shortest_path("Escuela", "Santa Lucía")
    assert path == [] and distance == float("inf")


def test_graph_path_to_itself_and_cheaper_detour():
    roads = Graph()
    roads.add_edge("A", "B", 10)
    roads.add_edge("A", "C", 2)
    roads.add_edge("C", "B", 3)
    assert roads.shortest_path("A", "A") == (["A"], 0)
    assert roads.shortest_path("A", "B") == (["A", "C", "B"], 5)


def test_graph_directed_edge_only_one_way():
    roads = Graph()
    roads.add_edge("A", "B", 1, undirected=False)
    assert roads.shortest_path("A", "B")[0] == ["A", "B"]
    assert roads.shortest_path("B", "A")[0] == []

