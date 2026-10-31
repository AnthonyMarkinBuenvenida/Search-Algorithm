"""The map that every search algorithm runs on.

A map is a rectangular grid. Each cell is identified by a (row, col) tuple and
holds one terrain tile:

    .  open ground   entering costs 1
    ~  mud           entering costs 5
    #  wall          cannot be entered

Movement is four-directional (up, right, down, left), so the map is really a
graph whose nodes are cells and whose edges join neighbouring open cells.
"""

from __future__ import annotations

import random
from pathlib import Path

Cell = tuple[int, int]

OPEN = "."
MUD = "~"
WALL = "#"
TILE_COST = {OPEN: 1, MUD: 5}

# Extra characters allowed in map text. They mark a position and stand on open
# ground. "*" means the start and goal share one cell.
START_CHAR = "S"
GOAL_CHAR = "G"
START_AND_GOAL_CHAR = "*"

MOVES = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
DEFAULT_DIRECTION_ORDER = "URDL"

MAX_SIDE = 100  # Larger maps would be unreadable on screen.


class InvalidInputError(ValueError):
    """Raised for a bad map, position, or option. The message is user-facing."""


class GridMap:
    """A grid of terrain tiles plus a start and a goal cell."""

    def __init__(
        self,
        tiles: list[list[str]],
        start: Cell,
        goal: Cell,
        direction_order: str = DEFAULT_DIRECTION_ORDER,
    ) -> None:
        if not tiles or not tiles[0]:
            raise InvalidInputError("The map is empty.")
        width = len(tiles[0])
        if any(len(row) != width for row in tiles):
            raise InvalidInputError("Every row of the map must have the same length.")
        if len(tiles) > MAX_SIDE or width > MAX_SIDE:
            raise InvalidInputError(f"Maps can be at most {MAX_SIDE} cells on each side.")
        for row in tiles:
            for tile in row:
                if tile not in (OPEN, MUD, WALL):
                    raise InvalidInputError(f"Unknown map tile: {tile!r}.")

        self.tiles = tiles
        self.rows = len(tiles)
        self.cols = width
        self.validate_endpoints(start, goal)
        self.start = start
        self.goal = goal
        self.direction_order = DEFAULT_DIRECTION_ORDER
        self.set_direction_order(direction_order)

    # ------------------------------------------------------------------
    # Building maps
    # ------------------------------------------------------------------

    @classmethod
    def from_text(cls, text: str) -> "GridMap":
        """Parse a map from text, one row per line. Blank lines are ignored."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise InvalidInputError("The map is empty.")

        tiles: list[list[str]] = []
        starts: list[Cell] = []
        goals: list[Cell] = []
        for row, line in enumerate(lines):
            tile_row = []
            for col, char in enumerate(line):
                if char in (START_CHAR, START_AND_GOAL_CHAR):
                    starts.append((row, col))
                if char in (GOAL_CHAR, START_AND_GOAL_CHAR):
                    goals.append((row, col))
                if char in (START_CHAR, GOAL_CHAR, START_AND_GOAL_CHAR):
                    tile_row.append(OPEN)
                elif char in (OPEN, MUD, WALL):
                    tile_row.append(char)
                else:
                    raise InvalidInputError(
                        f"Unknown character {char!r} at row {row}, column {col}. "
                        "Use . ~ # S G or *."
                    )
            tiles.append(tile_row)

        if len(starts) != 1:
            raise InvalidInputError(f"The map needs exactly one start, found {len(starts)}.")
        if len(goals) != 1:
            raise InvalidInputError(f"The map needs exactly one goal, found {len(goals)}.")
        return cls(tiles, starts[0], goals[0])

    @classmethod
    def from_file(cls, path: str | Path) -> "GridMap":
        """Load a map from a text file."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise InvalidInputError(f"Could not read map file: {error}") from error
        return cls.from_text(text)

    @classmethod
    def blank(cls, rows: int, cols: int) -> "GridMap":
        """An open map with the start and goal in opposite corners."""
        if rows < 1 or cols < 1:
            raise InvalidInputError("A map needs at least one row and one column.")
        tiles = [[OPEN] * cols for _ in range(rows)]
        return cls(tiles, (0, 0), (rows - 1, cols - 1))

    @classmethod
    def random(
        cls,
        rows: int,
        cols: int,
        wall_density: float = 0.25,
        mud_density: float = 0.10,
        seed: int | None = None,
    ) -> "GridMap":
        """A random map. Walls may happen to cut the goal off from the start."""
        if not (0 <= wall_density <= 1 and 0 <= mud_density <= 1):
            raise InvalidInputError("Densities must be between 0 and 1.")
        if wall_density + mud_density > 1:
            raise InvalidInputError("Wall and mud densities cannot add up to more than 1.")

        grid = cls.blank(rows, cols)
        rng = random.Random(seed)
        for row in range(rows):
            for col in range(cols):
                if (row, col) in (grid.start, grid.goal):
                    continue
                roll = rng.random()
                if roll < wall_density:
                    grid.tiles[row][col] = WALL
                elif roll < wall_density + mud_density:
                    grid.tiles[row][col] = MUD
        return grid

    def copy(self) -> "GridMap":
        """An independent copy, so the original can be edited safely."""
        tiles = [list(row) for row in self.tiles]
        return GridMap(tiles, self.start, self.goal, self.direction_order)

    def to_text(self) -> str:
        """The map as text, in the format `from_text` reads."""
        lines = []
        for row in range(self.rows):
            chars = []
            for col in range(self.cols):
                cell = (row, col)
                if cell == self.start and cell == self.goal:
                    chars.append(START_AND_GOAL_CHAR)
                elif cell == self.start:
                    chars.append(START_CHAR)
                elif cell == self.goal:
                    chars.append(GOAL_CHAR)
                else:
                    chars.append(self.tiles[row][col])
            lines.append("".join(chars))
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def check_cell(self, cell: object, label: str = "Position") -> None:
        """Raise InvalidInputError unless `cell` is a (row, col) inside the map."""
        is_pair = isinstance(cell, tuple) and len(cell) == 2
        if not is_pair or not all(type(part) is int for part in cell):
            raise InvalidInputError(f"{label} must be a (row, column) pair of integers.")
        row, col = cell
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise InvalidInputError(
                f"{label} {cell} is outside the map "
                f"({self.rows} rows by {self.cols} columns)."
            )

    def validate_endpoints(self, start: Cell, goal: Cell) -> None:
        """Raise InvalidInputError unless both cells can be stood on."""
        for label, cell in (("Start", start), ("Goal", goal)):
            self.check_cell(cell, label)
            if self.tile_at(cell) == WALL:
                raise InvalidInputError(f"{label} {cell} is on a wall.")

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def set_start(self, cell: Cell) -> None:
        self.validate_endpoints(cell, self.goal)
        self.start = cell

    def set_goal(self, cell: Cell) -> None:
        self.validate_endpoints(self.start, cell)
        self.goal = cell

    def set_tile(self, cell: Cell, tile: str) -> None:
        """Change one tile. The start and goal can never become walls."""
        self.check_cell(cell)
        if tile not in (OPEN, MUD, WALL):
            raise InvalidInputError(f"Unknown map tile: {tile!r}.")
        if tile == WALL and cell in (self.start, self.goal):
            raise InvalidInputError("The start and goal cannot be walls.")
        row, col = cell
        self.tiles[row][col] = tile

    def set_direction_order(self, order: str) -> None:
        """Set the order neighbours are visited in, e.g. "URDL"."""
        if sorted(order) != sorted(MOVES):
            raise InvalidInputError("Direction order must use each of U, R, D, L once.")
        self.direction_order = order

    # ------------------------------------------------------------------
    # Queries used by the search algorithms
    # ------------------------------------------------------------------

    def tile_at(self, cell: Cell) -> str:
        row, col = cell
        return self.tiles[row][col]

    def step_cost(self, cell: Cell) -> int:
        """The cost of moving into `cell`."""
        return TILE_COST[self.tile_at(cell)]

    def neighbors(self, cell: Cell) -> list[Cell]:
        """Cells reachable in one move, listed in `direction_order`."""
        row, col = cell
        result = []
        for direction in self.direction_order:
            d_row, d_col = MOVES[direction]
            next_row, next_col = row + d_row, col + d_col
            if 0 <= next_row < self.rows and 0 <= next_col < self.cols:
                if self.tiles[next_row][next_col] != WALL:
                    result.append((next_row, next_col))
        return result

    def path_cost(self, path: list[Cell]) -> int:
        """Total cost of a path. The first cell is free: we start there."""
        return sum(self.step_cost(cell) for cell in path[1:])

    def is_valid_path(self, path: list[Cell], start: Cell, goal: Cell) -> bool:
        """True if `path` runs from start to goal using only legal moves."""
        if not path or path[0] != start or path[-1] != goal:
            return False
        if len(set(path)) != len(path):
            return False
        return all(
            after in self.neighbors(before) for before, after in zip(path, path[1:])
        )
