"""Edge cases of the data structures: empty structures, one element and limits.

These tests complement tests/test_structures.py and do not need the API or the database.
"""

from app.structures.circular_doubly_list import CircularDoublyList
from app.structures.circular_list import CircularList
from app.structures.doubly_linked_list import DoublyLinkedList
from app.structures.linked_list import LinkedList


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
