from app.structures.avl import AVLTree
from app.structures.bst import BST
from app.structures.circular_doubly_list import CircularDoublyList
from app.structures.circular_list import CircularList
from app.structures.doubly_linked_list import DoublyLinkedList
from app.structures.graph import Graph
from app.structures.linked_list import LinkedList
from app.structures.nary_tree import NaryTree
from app.structures.queue import Queue
from app.structures.stack import Stack


def test_stack():
    stack = Stack()
    stack.push("route_v1")
    stack.push("route_v2")
    assert stack.pop() == "route_v2"
    assert stack.peek() == "route_v1"


def test_queue():
    queue = Queue()
    queue.enqueue("Juan")
    queue.enqueue("Ana")
    assert queue.dequeue() == "Juan"
    assert len(queue) == 1


def test_linked_list():
    stops = LinkedList()
    for name in ["El Encano", "La Laguna", "School"]:
        stops.append(name)
    assert stops.to_list() == ["El Encano", "La Laguna", "School"]


def test_doubly_linked_list():
    route = DoublyLinkedList()
    for name in ["A", "B", "C"]:
        route.append(name)
    assert route.forward() == ["A", "B", "C"]
    assert route.backward() == ["C", "B", "A"]


def test_circular_list():
    daily_routes = CircularList()
    daily_routes.append("Route 1")
    daily_routes.append("Route 2")
    assert daily_routes.cycle(4) == ["Route 1", "Route 2", "Route 1", "Route 2"]
    assert daily_routes.cycle(3, start_index=1) == ["Route 2", "Route 1", "Route 2"]
    assert daily_routes.tail.next is daily_routes.head  # real ring of nodes


def test_circular_doubly_list():
    drivers = CircularDoublyList()
    drivers.append("Carlos")
    drivers.append("Pedro")
    assert [drivers.next() for _ in range(3)] == ["Pedro", "Carlos", "Pedro"]
    assert drivers.prev() == "Carlos"
    assert drivers.find(lambda name: name == "Pedro") == "Pedro"
    assert drivers.next() == "Carlos"  # after the last comes the first
    assert drivers.head.prev.data == "Pedro"


def test_bst():
    tree = BST()
    for key in [50, 30, 70]:
        tree.insert(key, f"student-{key}")
    assert tree.search(30) == "student-30"
    assert tree.search(99) is None


def test_avl():
    tree = AVLTree()
    for value in [30, 20, 10, 25, 40, 50]:
        tree.insert(value, str(value))
    assert tree.search(25) == "25"
    # Inserting 30, 20, 10 forces a rotation, so the tree stays balanced.
    assert abs(tree.balance(tree.root)) <= 1


def test_nary_tree():
    tree = NaryTree("Institution")
    campus = tree.add_child(tree.root, "Main campus")
    grade = tree.add_child(campus, "8th grade")
    tree.add_child(grade, "Juan Pérez")
    assert tree.root.children[0].children[0].children[0].name == "Juan Pérez"


def test_graph():
    graph = Graph()
    graph.add_edge("A", "B", 2)
    graph.add_edge("B", "C", 3)
    graph.add_edge("A", "C", 10)
    assert graph.shortest_path("A", "C") == (["A", "B", "C"], 5)


def test_avl_prefix_search():
    tree = AVLTree()
    for name in ["juan perez", "valentina perez", "valeria ortiz", "sofia lopez"]:
        tree.insert(name, name.title())
    assert tree.prefix_search("val") == ["Valentina Perez", "Valeria Ortiz"]
    assert tree.prefix_search("zz") == []


def test_queue_is_linked_and_fifo():
    queue = Queue()
    for item in ("a", "b", "c"):
        queue.enqueue(item)
    assert queue.dequeue() == "a"
    queue.enqueue("d")
    assert queue.to_list() == ["b", "c", "d"]
    assert len(queue) == 3
    while not queue.is_empty():
        queue.dequeue()
    assert queue.dequeue() is None and queue.tail is None


def test_stack_is_linked_and_lifo():
    stack = Stack()
    for item in (1, 2, 3):
        stack.push(item)
    assert stack.to_list() == [3, 2, 1]
    assert stack.pop() == 3 and len(stack) == 2


def test_min_heap_orders_by_priority():
    from app.structures.min_heap import MinHeap

    heap = MinHeap()
    for priority in (5, 1, 4, 2, 3, 0):
        heap.push(priority, f"n{priority}")
    assert [heap.pop()[0] for _ in range(6)] == [0, 1, 2, 3, 4, 5]
    assert heap.pop() is None


def test_bst_delete_three_cases():
    tree = BST()
    for key in (50, 30, 70, 20, 40, 60, 80):
        tree.insert(key, str(key))
    assert tree.delete(20)  # leaf
    assert tree.delete(30)  # one child
    assert tree.delete(50)  # two children
    assert not tree.delete(999)
    assert tree.in_order() == [40, 60, 70, 80]
    assert tree.search(50) is None and tree.size == 4


def test_avl_delete_keeps_balance():
    tree = AVLTree()
    for key in range(1, 101):
        tree.insert(key, key)
    for key in range(1, 81):
        assert tree.delete(key)
    assert tree.in_order() == list(range(81, 101))
    assert tree.size == 20

    def check(node):
        if not node:
            return 0
        left, right = check(node.left), check(node.right)
        assert abs(left - right) <= 1
        return 1 + max(left, right)

    assert check(tree.root) <= 6


def test_attendance_matrix():
    from app.structures.attendance_matrix import ABSENT, PRESENT, AttendanceMatrix

    matrix = AttendanceMatrix(["ana", "luis"], ["lun", "mar", "mie"])
    matrix.fill_column("lun", ABSENT)
    matrix.set("ana", "lun", PRESENT)
    matrix.fill_column("mar", ABSENT)
    assert matrix.shape == (2, 3)
    assert matrix.row("ana") == ["P", "A", "-"]
    assert matrix.column("lun") == ["P", "A"]
    assert matrix.attendance_rate("ana") == 0.5
    assert matrix.attendance_rate("luis") == 0.0
