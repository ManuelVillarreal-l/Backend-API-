"""Edge cases of the data structures: empty structures, one element and limits.

These tests complement tests/test_structures.py and do not need the API or the database.
"""

from app.structures.circular_doubly_list import CircularDoublyList
from app.structures.circular_list import CircularList


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
