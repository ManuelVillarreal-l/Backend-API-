"""Attendance matrix (2D array): rows = students, columns = school days.

Use in RutaSegura: daily attendance of the students of a route.
Each cell holds a code:
    "P" present (boarded the bus that day)
    "A" absent  (there was a trip that day but the student did not board)
    "-" no trip that day
Access to a cell by (row, column) is O(1) because rows and columns are indexed.
"""

PRESENT = "P"
ABSENT = "A"
NO_TRIP = "-"


class AttendanceMatrix:
    def __init__(self, row_keys: list, column_keys: list, fill: str = NO_TRIP):
        self.row_keys = list(row_keys)
        self.column_keys = list(column_keys)
        self.row_index = {key: i for i, key in enumerate(self.row_keys)}
        self.column_index = {key: j for j, key in enumerate(self.column_keys)}
        self.cells = [[fill for _ in self.column_keys] for _ in self.row_keys]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.row_keys), len(self.column_keys)

    def set(self, row_key, column_key, value: str) -> None:
        self.cells[self.row_index[row_key]][self.column_index[column_key]] = value

    def get(self, row_key, column_key) -> str:
        return self.cells[self.row_index[row_key]][self.column_index[column_key]]

    def fill_column(self, column_key, value: str) -> None:
        j = self.column_index[column_key]
        for row in self.cells:
            row[j] = value

    def row(self, row_key) -> list:
        return list(self.cells[self.row_index[row_key]])

    def column(self, column_key) -> list:
        j = self.column_index[column_key]
        return [row[j] for row in self.cells]

    def count_row(self, row_key, value: str) -> int:
        return sum(1 for cell in self.cells[self.row_index[row_key]] if cell == value)

    def count_column(self, column_key, value: str) -> int:
        j = self.column_index[column_key]
        return sum(1 for row in self.cells if row[j] == value)

    def attendance_rate(self, row_key) -> float | None:
        """Present / (present + absent) for one student; None if there were no trips."""
        present = self.count_row(row_key, PRESENT)
        absent = self.count_row(row_key, ABSENT)
        total = present + absent
        return round(present / total, 3) if total else None

    def to_list(self) -> list[list[str]]:
        return [list(row) for row in self.cells]
