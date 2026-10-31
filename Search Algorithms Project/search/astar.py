"""A* Search.

A* always expands the frontier node with the lowest

    f(n) = g(n) + h(n)

where g(n) is the actual cost from the start to n, and h(n) is the heuristic's
estimate of the cost from n to the goal. So f(n) estimates the total cost of a
route through n: g keeps the search honest about distance already paid, and h
pulls it towards the goal.

With an admissible heuristic (see heuristics.py) the path returned has the
lowest possible cost, including on maps with mud.
"""

from __future__ import annotations

import heapq
from itertools import count

from .grid_map import Cell, GridMap
from .heuristics import DEFAULT_HEURISTIC, get_heuristic
from .result import SearchResult, SearchStep, build_result


def astar(
    grid: GridMap,
    start: Cell,
    goal: Cell,
    heuristic: str = DEFAULT_HEURISTIC,
) -> SearchResult:
    grid.validate_endpoints(start, goal)
    estimate = get_heuristic(heuristic)

    # Queue entries sort by f. Ties prefer the lower h, the node that seems
    # closer to the goal. `order` breaks any remaining tie by age.
    order = count()
    start_h = estimate(start, goal)
    frontier = [(start_h, start_h, next(order), 0, start)]

    came_from: dict[Cell, Cell | None] = {start: None}
    best_cost: dict[Cell, int] = {start: 0}  # Cheapest known g for each node.
    steps: list[SearchStep] = []
    path_updates = 0

    while frontier:
        f, h, _, g, current = heapq.heappop(frontier)

        # heapq cannot change an entry's priority, so an improved route adds a
        # new entry instead. An entry costing more than the best g is out of date.
        if g > best_cost[current]:
            continue

        detail = f"g={g} h={h:.1f} f={f:.1f}"
        if current == goal:
            steps.append(SearchStep(current, (), len(frontier), detail))
            return build_result(
                "A*", grid, start, goal, True, came_from, steps, heuristic, path_updates
            )

        discovered = []
        for neighbor in grid.neighbors(current):
            new_cost = g + grid.step_cost(neighbor)
            is_new = neighbor not in best_cost
            if is_new or new_cost < best_cost[neighbor]:
                if not is_new:
                    path_updates += 1  # A better route to a known node.
                best_cost[neighbor] = new_cost
                came_from[neighbor] = current
                neighbor_h = estimate(neighbor, goal)
                entry = (new_cost + neighbor_h, neighbor_h, next(order), new_cost, neighbor)
                heapq.heappush(frontier, entry)
                discovered.append(neighbor)
        steps.append(SearchStep(current, tuple(discovered), len(frontier), detail))

    return build_result(
        "A*", grid, start, goal, False, came_from, steps, heuristic, path_updates
    )
