"""Start the search demo.

    python main.py                                opens the graphical interface
    python main.py --console                      opens the text menu
    python main.py --map maps/3_multiple_paths.txt --algorithm all
                                                  runs once and prints the result
"""

from __future__ import annotations

import argparse
import sys

from console import describe_result, format_table, render, run_console, LEGEND
from search import ALGORITHMS, GridMap, InvalidInputError, compare_all, run_search
from search.heuristics import DEFAULT_HEURISTIC, HEURISTICS
from search.runner import comparison_rows, observations


def run_once(map_path: str, algorithm: str, heuristic: str) -> None:
    """Non-interactive mode: one map, one report, then exit."""
    grid = GridMap.from_file(map_path)
    if algorithm == "all":
        results = compare_all(grid, heuristic=heuristic)
        print(format_table(comparison_rows(results)))
        print(f"A* heuristic: {heuristic}")
        for note in observations(results):
            print(f"- {note}")
        return
    result = run_search(algorithm, grid, heuristic=heuristic)
    print(render(grid, result))
    print(LEGEND)
    print(describe_result(result))


def run_gui_or_console() -> None:
    """Open the GUI, or the console if this Python has no usable Tkinter."""
    try:
        import tkinter

        from gui import run_gui
    except ImportError:
        print("Tkinter is not installed, so the console version is starting.")
        run_console()
        return
    try:
        run_gui()
    except tkinter.TclError as error:
        print(f"Could not open a window ({error}), so the console version is starting.")
        run_console()


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BFS, DFS and A* search on a grid map.")
    parser.add_argument("--console", action="store_true", help="use the text menu")
    parser.add_argument("--map", help="map file to run once, without any menu")
    parser.add_argument(
        "--algorithm", default="all", choices=[*ALGORITHMS, "all"],
        help="algorithm to use with --map (default: all)",
    )
    parser.add_argument(
        "--heuristic", default=DEFAULT_HEURISTIC, choices=list(HEURISTICS),
        help="A* heuristic (default: %(default)s)",
    )
    options = parser.parse_args(arguments)

    try:
        if options.map:
            run_once(options.map, options.algorithm, options.heuristic)
        elif options.console:
            run_console()
        else:
            run_gui_or_console()
    except InvalidInputError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
