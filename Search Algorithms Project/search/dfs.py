"""Depth-First Search.

DFS keeps its frontier in a last-in, first-out stack, so the newest node is
always handled next. It follows one branch as far as it can, and only when that
branch is exhausted does the stack hand back an older node: that is backtracking.

DFS stops at the first route it stumbles on, so it does not guarantee the
shortest path. Which route it finds depends heavily on the neighbour order and
on the layout of the map.
"""

from __future__ import annotations

from .grid_map import Cell, GridMap
from .result import SearchResult, SearchStep, build_result


def dfs(grid: GridMap, start: Cell, goal: Cell) -> SearchResult:
    grid.validate_endpoints(start, goal)

    # Each entry remembers the node that pushed it, because a node can be pushed
    # by several neighbours before it is finally visited.
    stack: list[tuple[Cell, Cell | None]] = [(start, None)]
    came_from: dict[Cell, Cell | None] = {}  # Also the visited set.
    steps: list[SearchStep] = []

    while stack:
        current, parent = stack.pop()

        # A node is marked when popped, not when pushed. Marking on push would
        # stop a deeper branch from reaching it, and the search would no longer
        # be truly depth-first.
        if current in came_from:
            continue
        came_from[current] = parent

        if current == goal:
            steps.append(SearchStep(current, (), len(stack)))
            return build_result("DFS", grid, start, goal, True, came_from, steps)

        discovered = []
        # Push in reverse so the first neighbour listed is popped first.
        for neighbor in reversed(grid.neighbors(current)):
            if neighbor not in came_from:
                stack.append((neighbor, current))
                discovered.append(neighbor)
        steps.append(SearchStep(current, tuple(discovered), len(stack)))

    return build_result("DFS", grid, start, goal, False, came_from, steps)
