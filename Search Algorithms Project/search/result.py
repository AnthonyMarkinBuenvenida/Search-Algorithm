"""Data shared by all three algorithms: what a search did and what it found."""

from __future__ import annotations

from dataclasses import dataclass, field

from .grid_map import Cell, GridMap


@dataclass(frozen=True)
class SearchStep:
    """One expansion: a node leaves the frontier and its neighbours are examined.

    The GUI replays these steps to animate the search.
    """

    cell: Cell
    discovered: tuple[Cell, ...]  # Neighbours added to the frontier by this step.
    frontier_size: int
    detail: str = ""  # Extra values to show, such as A*'s g, h and f.


@dataclass
class SearchResult:
    """The outcome of running one algorithm on one map."""

    algorithm: str
    start: Cell
    goal: Cell
    found: bool
    path: list[Cell]  # Empty when the goal was not reached.
    path_cost: int | None  # None when the goal was not reached.
    steps: list[SearchStep]
    heuristic: str = "None"
    path_updates: int = 0  # Times A* replaced a route with a cheaper one.
    execution_ms: float = 0.0  # Filled in by runner.run_search.
    message: str = field(default="")

    @property
    def nodes_explored(self) -> int:
        return len(self.steps)

    @property
    def path_length(self) -> int | None:
        """Number of moves in the path, or None when the goal was not reached."""
        return len(self.path) - 1 if self.found else None


def reconstruct_path(came_from: dict[Cell, Cell | None], goal: Cell) -> list[Cell]:
    """Walk parent links back from the goal, then reverse to get start -> goal."""
    path = [goal]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def build_result(
    algorithm: str,
    grid: GridMap,
    start: Cell,
    goal: Cell,
    found: bool,
    came_from: dict[Cell, Cell | None],
    steps: list[SearchStep],
    heuristic: str = "None",
    path_updates: int = 0,
) -> SearchResult:
    """Package a finished search into a SearchResult."""
    path = reconstruct_path(came_from, goal) if found else []
    path_cost = grid.path_cost(path) if found else None
    if found:
        message = f"Goal reached in {len(path) - 1} moves at a cost of {path_cost}."
    else:
        message = f"No path exists: the goal cannot be reached from {start}."
    return SearchResult(
        algorithm=algorithm,
        start=start,
        goal=goal,
        found=found,
        path=path,
        path_cost=path_cost,
        steps=steps,
        heuristic=heuristic,
        path_updates=path_updates,
        message=message,
    )
