"""Breadth-First Search.

BFS keeps its frontier in a first-in, first-out queue, so nodes leave in the
order they were discovered. All nodes one move from the start are handled, then
all nodes two moves away, and so on. The first time the goal leaves the queue,
no route with fewer moves can exist.

BFS counts moves and ignores terrain cost, so its path has the fewest moves but
is not always the cheapest.
"""

from __future__ import annotations

from collections import deque

from .grid_map import Cell, GridMap
from .result import SearchResult, SearchStep, build_result


def bfs(grid: GridMap, start: Cell, goal: Cell) -> SearchResult:
    grid.validate_endpoints(start, goal)

    frontier = deque([start])
    # came_from doubles as the visited set. A node is marked when it is first
    # discovered, so it can never enter the queue twice.
    came_from: dict[Cell, Cell | None] = {start: None}
    steps: list[SearchStep] = []

    while frontier:
        current = frontier.popleft()

        if current == goal:
            steps.append(SearchStep(current, (), len(frontier)))
            return build_result("BFS", grid, start, goal, True, came_from, steps)

        discovered = []
        for neighbor in grid.neighbors(current):
            if neighbor not in came_from:
                came_from[neighbor] = current
                frontier.append(neighbor)
                discovered.append(neighbor)
        steps.append(SearchStep(current, tuple(discovered), len(frontier)))

    return build_result("BFS", grid, start, goal, False, came_from, steps)
