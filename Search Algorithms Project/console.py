"""Console version of the program, offering the same core features as the GUI."""

from __future__ import annotations

from sample_maps import sample_maps, starting_map
from search import ALGORITHMS, GridMap, InvalidInputError, compare_all, run_search
from search.grid_map import MUD, OPEN, WALL
from search.heuristics import DEFAULT_HEURISTIC, HEURISTICS
from search.result import SearchResult
from search.runner import comparison_rows, format_path, observations

PATH_MARK = "o"
VISITED_MARK = ":"

MENU = """
 1) Show map              6) Add or remove a wall
 2) Choose a sample map   7) Run one algorithm
 3) Load a map file       8) Compare all three
 4) Random map            9) Choose A* heuristic
 5) Set start and goal    0) Quit"""

LEGEND = (
    f"S start   G goal   {WALL} wall   {MUD} mud (cost 5)   {OPEN} open (cost 1)   "
    f"{VISITED_MARK} explored   {PATH_MARK} path"
)


def render(grid: GridMap, result: SearchResult | None = None) -> str:
    """Draw the map as text, with a search result on top if one is given."""
    explored = {step.cell for step in result.steps} if result else set()
    path = set(result.path) if result else set()

    lines = ["    " + "".join(str(col % 10) for col in range(grid.cols))]
    for row in range(grid.rows):
        chars = []
        for col in range(grid.cols):
            cell = (row, col)
            if cell == grid.start and cell == grid.goal:
                chars.append("*")
            elif cell == grid.start:
                chars.append("S")
            elif cell == grid.goal:
                chars.append("G")
            elif cell in path:
                chars.append(PATH_MARK)
            elif cell in explored:
                chars.append(VISITED_MARK)
            else:
                chars.append(grid.tile_at(cell))
        lines.append(f"{row:>3} " + "".join(chars))
    return "\n".join(lines)


def format_table(rows: list[list[str]]) -> str:
    """Line up comparison rows into a text table."""
    table = [["Metric", *ALGORITHMS]] + rows
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    lines = ["  ".join(text.ljust(width) for text, width in zip(row, widths)) for row in table]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines)


def describe_result(result: SearchResult) -> str:
    """The results panel, as text."""
    lines = [
        f"Algorithm:      {result.algorithm}",
        f"Goal reached:   {'Yes' if result.found else 'No'}",
        f"Nodes explored: {result.nodes_explored}",
    ]
    if result.found:
        lines.append(f"Path length:    {result.path_length} moves")
        lines.append(f"Path cost:      {result.path_cost}")
    lines.append(f"Execution time: {result.execution_ms:.3f} ms")
    if result.algorithm == "A*":
        lines.append(f"Heuristic:      {result.heuristic}")
        lines.append(f"Route updates:  {result.path_updates}")
    lines.append(f"Path:           {format_path(result.path, limit=12)}")
    lines.append(result.message)
    return "\n".join(lines)


def read_cell(prompt: str) -> tuple[int, int]:
    """Ask for "row col". Raises InvalidInputError if it is not two integers."""
    parts = input(prompt).replace(",", " ").split()
    try:
        row, col = (int(part) for part in parts)
    except ValueError:
        raise InvalidInputError('Enter a position as two whole numbers, e.g. "3 7".') from None
    return row, col


def read_int(prompt: str) -> int:
    text = input(prompt).strip()
    try:
        return int(text)
    except ValueError:
        raise InvalidInputError(f"{text!r} is not a whole number.") from None


def choose(title: str, options: list[str]) -> str:
    """Show a numbered list and return the chosen option."""
    if not options:
        raise InvalidInputError("There is nothing to choose from.")
    print(title)
    for number, option in enumerate(options, start=1):
        print(f"  {number}) {option}")
    choice = read_int("Choice: ")
    if not 1 <= choice <= len(options):
        raise InvalidInputError(f"Choose a number from 1 to {len(options)}.")
    return options[choice - 1]


def toggle_wall(grid: GridMap, cell: tuple[int, int]) -> str:
    grid.check_cell(cell)
    if grid.tile_at(cell) == WALL:
        grid.set_tile(cell, OPEN)
        return f"Removed the wall at {cell}."
    grid.set_tile(cell, WALL)
    return f"Added a wall at {cell}."


def run_console() -> None:
    """The interactive menu loop. Bad input prints a message and never crashes."""
    maps = sample_maps()
    grid = starting_map()
    heuristic = DEFAULT_HEURISTIC
    print("BFS, DFS and A* search demo")
    print(render(grid))
    print(LEGEND)

    while True:
        print(MENU)
        try:
            action = input("Choice: ").strip()
            if action == "0":
                return
            elif action == "1":
                print(render(grid))
                print(LEGEND)
            elif action == "2":
                grid = GridMap.from_file(maps[choose("Sample maps:", list(maps))])
                print(render(grid))
            elif action == "3":
                grid = GridMap.from_file(input("Path to map file: ").strip())
                print(render(grid))
            elif action == "4":
                rows = read_int("Rows: ")
                cols = read_int("Columns: ")
                grid = GridMap.random(rows, cols)
                print(render(grid))
            elif action == "5":
                new_start = read_cell("Start (row col): ")
                new_goal = read_cell("Goal (row col): ")
                grid.validate_endpoints(new_start, new_goal)
                grid.start, grid.goal = new_start, new_goal
                print(render(grid))
            elif action == "6":
                print(toggle_wall(grid, read_cell("Cell (row col): ")))
                print(render(grid))
            elif action == "7":
                name = choose("Algorithms:", list(ALGORITHMS))
                result = run_search(name, grid, heuristic=heuristic)
                print(render(grid, result))
                print(describe_result(result))
            elif action == "8":
                results = compare_all(grid, heuristic=heuristic)
                print(format_table(comparison_rows(results)))
                print(f"A* heuristic: {heuristic}")
                for note in observations(results):
                    print(f"- {note}")
            elif action == "9":
                heuristic = choose("Heuristics:", list(HEURISTICS))
                print(f"A* will use: {heuristic}")
            else:
                print("Please choose an option from the menu.")
        except InvalidInputError as error:
            print(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print()
            return
