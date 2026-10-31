"""Run the algorithms, time them, and turn the results into a comparison.

The GUI, the console and the scenario script all go through this module, so they
report numbers in exactly the same way.
"""

from __future__ import annotations

import statistics
import time

from .astar import astar
from .bfs import bfs
from .dfs import dfs
from .grid_map import Cell, GridMap, InvalidInputError
from .heuristics import DEFAULT_HEURISTIC, get_heuristic
from .result import SearchResult

ALGORITHMS = {"BFS": bfs, "DFS": dfs, "A*": astar}

GUARANTEES = {
    "BFS": "Yes, for equal edge costs",
    "DFS": "No, in general",
    "A*": "Yes, under suitable conditions",
}

# A single run of a small map takes microseconds, so one measurement is mostly
# noise. The reported time is the median of several identical runs.
TIMING_REPEATS = 5


def run_search(
    name: str,
    grid: GridMap,
    start: Cell | None = None,
    goal: Cell | None = None,
    heuristic: str = DEFAULT_HEURISTIC,
    repeats: int = TIMING_REPEATS,
) -> SearchResult:
    """Run one algorithm by name. Start and goal default to the map's own."""
    if name not in ALGORITHMS:
        options = ", ".join(ALGORITHMS)
        raise InvalidInputError(f"Unknown algorithm {name!r}. Choose from: {options}.")
    get_heuristic(heuristic)  # Reject a bad name even when BFS or DFS was chosen.

    start = grid.start if start is None else start
    goal = grid.goal if goal is None else goal
    keyword_args = {"heuristic": heuristic} if name == "A*" else {}

    timings = []
    result = None
    for _ in range(repeats):
        began = time.perf_counter()
        result = ALGORITHMS[name](grid, start, goal, **keyword_args)
        timings.append((time.perf_counter() - began) * 1000)
    result.execution_ms = statistics.median(timings)
    return result


def compare_all(
    grid: GridMap,
    start: Cell | None = None,
    goal: Cell | None = None,
    heuristic: str = DEFAULT_HEURISTIC,
) -> dict[str, SearchResult]:
    """Run all three algorithms on the same map and problem."""
    return {name: run_search(name, grid, start, goal, heuristic) for name in ALGORITHMS}


def _or_dash(value: object) -> str:
    return "-" if value is None else str(value)


def comparison_rows(results: dict[str, SearchResult]) -> list[list[str]]:
    """Comparison table rows: the metric name, then one value per algorithm."""
    metrics = [
        ("Nodes explored", lambda r: str(r.nodes_explored)),
        ("Path length (moves)", lambda r: _or_dash(r.path_length)),
        ("Path cost", lambda r: _or_dash(r.path_cost)),
        ("Execution time (ms)", lambda r: f"{r.execution_ms:.3f}"),
        ("Path found", lambda r: "Yes" if r.found else "No"),
        ("Guarantees shortest path", lambda r: GUARANTEES[r.algorithm]),
    ]
    return [
        [label] + [read(results[name]) for name in ALGORITHMS]
        for label, read in metrics
    ]


def _names_with_lowest(results: list[SearchResult], read) -> str:
    lowest = min(read(result) for result in results)
    names = [r.algorithm for r in results if read(r) == lowest]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]


def observations(results: dict[str, SearchResult]) -> list[str]:
    """Plain-language notes on this run, worked out from the measured results."""
    all_results = list(results.values())
    found = [result for result in all_results if result.found]
    if not found:
        counts = ", ".join(f"{r.algorithm} {r.nodes_explored}" for r in all_results)
        return [
            "No path exists, so each algorithm searched everything it could reach "
            f"before giving up (nodes explored: {counts})."
        ]

    notes = []
    fewest = min(r.nodes_explored for r in all_results)
    names = _names_with_lowest(all_results, lambda r: r.nodes_explored)
    notes.append(f"Fewest nodes explored: {names} ({fewest}).")

    moves = {r.path_length for r in found}
    costs = {r.path_cost for r in found}
    if len(moves) == 1 and len(costs) == 1:
        notes.append("All three returned paths of equal length and cost on this map.")
    else:
        notes.append(
            f"Fewest moves: {_names_with_lowest(found, lambda r: r.path_length)} "
            f"({min(moves)}). Lowest cost: "
            f"{_names_with_lowest(found, lambda r: r.path_cost)} ({min(costs)})."
        )

    bfs_result, astar_result = results.get("BFS"), results.get("A*")
    if bfs_result and astar_result and bfs_result.path_cost != astar_result.path_cost:
        notes.append(
            "BFS counts moves and ignores terrain, so its path crossed costlier "
            "ground than the one A* chose."
        )
    return notes


def format_path(path: list[Cell], limit: int | None = None) -> str:
    """The path as text, shortened in the middle when `limit` cells is exceeded."""
    if not path:
        return "(no path)"
    cells = [f"({row},{col})" for row, col in path]
    if limit is not None and len(cells) > limit:
        half = limit // 2
        hidden = len(cells) - 2 * half
        cells = cells[:half] + [f"... {hidden} more ..."] + cells[-half:]
    return " -> ".join(cells)
