"""Heuristics for A*: h(n), an estimate of the cost from n to the goal.

A* returns an optimal path when h never overestimates the true remaining cost
(it is "admissible"). All three below qualify on this map, because every move
travels one cell in a straight line and costs at least 1.

They are also "consistent": h never falls by more than the cost of a move. That
means a node's cost is final once it leaves the priority queue.
"""

from __future__ import annotations

import math

from .grid_map import Cell, InvalidInputError


def manhattan(cell: Cell, goal: Cell) -> float:
    """Rows plus columns to the goal: exact on an open four-directional grid."""
    return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])


def euclidean(cell: Cell, goal: Cell) -> float:
    """Straight-line distance. Admissible, but lower than Manhattan here."""
    return math.hypot(cell[0] - goal[0], cell[1] - goal[1])


def zero(cell: Cell, goal: Cell) -> float:
    """No estimate at all. A* then behaves exactly like Dijkstra's algorithm."""
    return 0


HEURISTICS = {
    "Manhattan": manhattan,
    "Euclidean": euclidean,
    "Zero (Dijkstra)": zero,
}
DEFAULT_HEURISTIC = "Manhattan"


def get_heuristic(name: str):
    if name not in HEURISTICS:
        options = ", ".join(HEURISTICS)
        raise InvalidInputError(f"Unknown heuristic {name!r}. Choose from: {options}.")
    return HEURISTICS[name]
