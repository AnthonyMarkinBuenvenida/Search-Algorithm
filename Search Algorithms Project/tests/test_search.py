"""Tests for the map and the three search algorithms.

Run from the project folder with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import console  # noqa: E402
import main as main_module  # noqa: E402
import sample_maps  # noqa: E402
from search import ALGORITHMS, GridMap, InvalidInputError, astar, bfs, compare_all, dfs, run_search  # noqa: E402
from search.grid_map import WALL  # noqa: E402
from search.heuristics import HEURISTICS  # noqa: E402
from search.runner import comparison_rows, format_path, observations  # noqa: E402

MAPS = PROJECT / "maps"


def load(name: str) -> GridMap:
    return GridMap.from_file(MAPS / name)


def fewest_moves_and_cheapest(grid: GridMap, start, goal):
    """An independent answer key: Bellman-Ford style relaxation, no shortcuts.

    Repeatedly relaxes every edge until nothing improves. It shares no code with
    the searches, so agreement with it is real evidence they are right.
    """
    infinity = float("inf")
    cells = [
        (row, col)
        for row in range(grid.rows)
        for col in range(grid.cols)
        if grid.tiles[row][col] != WALL
    ]
    moves = {cell: infinity for cell in cells}
    costs = {cell: infinity for cell in cells}
    moves[start] = costs[start] = 0
    changed = True
    while changed:
        changed = False
        for cell in cells:
            for neighbor in grid.neighbors(cell):
                if moves[cell] + 1 < moves[neighbor]:
                    moves[neighbor] = moves[cell] + 1
                    changed = True
                new_cost = costs[cell] + grid.step_cost(neighbor)
                if new_cost < costs[neighbor]:
                    costs[neighbor] = new_cost
                    changed = True
    return moves[goal], costs[goal]


class ScenarioTests(unittest.TestCase):
    """The six scenarios the assignment requires."""

    def assert_all_find_valid_paths(self, grid: GridMap) -> dict:
        results = compare_all(grid)
        for name, result in results.items():
            with self.subTest(algorithm=name):
                self.assertTrue(result.found)
                self.assertTrue(grid.is_valid_path(result.path, grid.start, grid.goal))
                self.assertEqual(result.path_cost, grid.path_cost(result.path))
        return results

    def test_1_simple_path(self):
        grid = load("1_simple_path.txt")
        results = self.assert_all_find_valid_paths(grid)
        self.assertEqual(results["BFS"].path_length, 15)  # 5 rows + 10 columns away.
        self.assertEqual(results["A*"].path_cost, 15)

    def test_2_direct_route_blocked(self):
        grid = load("2_obstacle_filled.txt")
        results = self.assert_all_find_valid_paths(grid)
        straight_line = abs(grid.start[1] - grid.goal[1]) + abs(grid.start[0] - grid.goal[0])
        self.assertGreater(results["BFS"].path_length, straight_line)
        self.assertEqual(results["BFS"].path_length, results["A*"].path_length)

    def test_3_multiple_paths_give_three_different_routes(self):
        grid = load("3_multiple_paths.txt")
        results = self.assert_all_find_valid_paths(grid)
        self.assertEqual((results["BFS"].path_length, results["BFS"].path_cost), (22, 82))
        self.assertEqual((results["DFS"].path_length, results["DFS"].path_cost), (30, 70))
        self.assertEqual((results["A*"].path_length, results["A*"].path_cost), (26, 26))

    def test_4_unreachable_goal(self):
        grid = load("4_unreachable.txt")
        for name, result in compare_all(grid).items():
            with self.subTest(algorithm=name):
                self.assertFalse(result.found)
                self.assertEqual(result.path, [])
                self.assertIsNone(result.path_cost)
                self.assertIn("No path exists", result.message)

    def test_5_start_equals_goal(self):
        grid = load("5_start_equals_goal.txt")
        for name, result in compare_all(grid).items():
            with self.subTest(algorithm=name):
                self.assertTrue(result.found)
                self.assertEqual(result.path, [grid.start])
                self.assertEqual(result.path_length, 0)
                self.assertEqual(result.path_cost, 0)
                self.assertEqual(result.nodes_explored, 1)

    def test_6_invalid_map_text(self):
        bad_maps = {
            "empty": "",
            "only blank lines": "\n   \n",
            "uneven rows": "S..\n..\n..G",
            "unknown character": "S.x\n..G",
            "no start": "...\n..G",
            "no goal": "S..\n...",
            "two starts": "S.S\n..G",
            "two goals": "SGG\n...",
            "too large": "S" + "." * 200 + "G",
        }
        for label, text in bad_maps.items():
            with self.subTest(label), self.assertRaises(InvalidInputError):
                GridMap.from_text(text)

    def test_6_invalid_map_file(self):
        with self.assertRaises(InvalidInputError):
            GridMap.from_file(MAPS / "invalid" / "uneven_rows.txt")
        with self.assertRaises(InvalidInputError):
            GridMap.from_file(MAPS / "does_not_exist.txt")
        with tempfile.TemporaryDirectory() as folder:
            binary_file = Path(folder) / "binary.txt"
            binary_file.write_bytes(b"\xff\xfe\x00\x81")
            with self.assertRaises(InvalidInputError):
                GridMap.from_file(binary_file)

    def test_6_invalid_positions(self):
        grid = GridMap.from_text("S.#\n..G")
        bad_positions = [
            (-1, 0), (0, 3), (2, 0), (0, 2),  # Three outside the map, one on a wall.
            (0,), (0, 1, 2), "0,0", None, (1.0, 1), (True, 0),
        ]
        for position in bad_positions:
            for name in ALGORITHMS:
                with self.subTest(position=position, algorithm=name):
                    with self.assertRaises(InvalidInputError):
                        ALGORITHMS[name](grid, position, grid.goal)
                    with self.assertRaises(InvalidInputError):
                        ALGORITHMS[name](grid, grid.start, position)

    def test_6_invalid_options(self):
        grid = GridMap.from_text("S.G")
        with self.assertRaises(InvalidInputError):
            run_search("Dijkstra", grid)
        with self.assertRaises(InvalidInputError):
            run_search("BFS", grid, heuristic="Nonsense")
        with self.assertRaises(InvalidInputError):
            astar(grid, grid.start, grid.goal, heuristic="Nonsense")
        with self.assertRaises(InvalidInputError):
            grid.set_direction_order("UUDD")


class AlgorithmPropertyTests(unittest.TestCase):
    """Claims about each algorithm, checked against the independent answer key."""

    def random_maps(self):
        """400 reproducible maps of varied size and density."""
        for seed in range(400):
            rows = 3 + seed % 10
            cols = 3 + (seed * 7) % 13
            wall_density = (seed % 5) * 0.1
            yield seed, GridMap.random(rows, cols, wall_density, 0.2, seed=seed)

    def test_random_maps_match_answer_key(self):
        reachable = unreachable = 0
        for seed, grid in self.random_maps():
            moves, cost = fewest_moves_and_cheapest(grid, grid.start, grid.goal)
            results = compare_all(grid)
            with self.subTest(seed=seed):
                if moves == float("inf"):
                    unreachable += 1
                    for result in results.values():
                        self.assertFalse(result.found)
                    continue
                reachable += 1
                for result in results.values():
                    self.assertTrue(result.found)
                    self.assertTrue(grid.is_valid_path(result.path, grid.start, grid.goal))
                self.assertEqual(results["BFS"].path_length, moves)
                self.assertEqual(results["A*"].path_cost, cost)
                self.assertGreaterEqual(results["DFS"].path_length, moves)
        # Guard against a test that silently never checks one of the two cases.
        self.assertGreater(reachable, 100)
        self.assertGreater(unreachable, 20)

    def test_every_heuristic_finds_the_optimal_cost(self):
        for seed, grid in self.random_maps():
            _moves, cost = fewest_moves_and_cheapest(grid, grid.start, grid.goal)
            if cost == float("inf"):
                continue
            for heuristic in HEURISTICS:
                with self.subTest(seed=seed, heuristic=heuristic):
                    result = astar(grid, grid.start, grid.goal, heuristic)
                    self.assertEqual(result.path_cost, cost)

    def test_heuristics_are_admissible_and_consistent(self):
        grid = GridMap.random(12, 12, 0.2, 0.3, seed=11)
        for name, estimate in HEURISTICS.items():
            for row in range(grid.rows):
                for col in range(grid.cols):
                    cell = (row, col)
                    if grid.tile_at(cell) == WALL:
                        continue
                    _moves, true_cost = fewest_moves_and_cheapest(grid, cell, grid.goal)
                    with self.subTest(heuristic=name, cell=cell):
                        if true_cost != float("inf"):
                            self.assertLessEqual(estimate(cell, grid.goal), true_cost + 1e-9)
                        for neighbor in grid.neighbors(cell):
                            drop = estimate(cell, grid.goal) - estimate(neighbor, grid.goal)
                            self.assertLessEqual(drop, grid.step_cost(neighbor) + 1e-9)

    def test_nodes_are_never_expanded_twice(self):
        for seed, grid in self.random_maps():
            for name, result in compare_all(grid).items():
                with self.subTest(seed=seed, algorithm=name):
                    explored = [step.cell for step in result.steps]
                    self.assertEqual(len(explored), len(set(explored)))

    def test_bfs_explores_in_order_of_distance(self):
        grid = load("2_obstacle_filled.txt")
        distances = [
            fewest_moves_and_cheapest(grid, grid.start, step.cell)[0]
            for step in bfs(grid, grid.start, grid.goal).steps
        ]
        self.assertEqual(distances, sorted(distances))

    def test_dfs_goes_deep_before_backtracking(self):
        # The first neighbour tried is "up", so DFS runs to the top row at once.
        grid = GridMap.from_text("...\n...\n...\nS.G")
        explored = [step.cell for step in dfs(grid, grid.start, grid.goal).steps]
        self.assertEqual(explored[:4], [(3, 0), (2, 0), (1, 0), (0, 0)])

    def test_dfs_can_return_a_longer_path_than_bfs(self):
        grid = load("1_simple_path.txt")
        self.assertGreater(
            dfs(grid, grid.start, grid.goal).path_length,
            bfs(grid, grid.start, grid.goal).path_length,
        )

    def test_neighbour_order_changes_the_dfs_result(self):
        grid = load("1_simple_path.txt")
        first = dfs(grid, grid.start, grid.goal)
        grid.set_direction_order("DRUL")
        second = dfs(grid, grid.start, grid.goal)
        self.assertNotEqual(first.path, second.path)
        self.assertNotEqual(first.path_length, second.path_length)

    def test_astar_replaces_a_route_when_a_better_one_appears(self):
        # The heuristic draws A* towards the goal along a costlier route first.
        # A cheaper route to an already-known cell turns up later and must win.
        grid = GridMap.from_text("S.~#.\n~~~..\n~..~G")
        result = astar(grid, grid.start, grid.goal, "Manhattan")
        self.assertGreater(result.path_updates, 0)
        self.assertEqual(result.path_cost, 14)
        self.assertEqual(
            result.path, [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2), (2, 3), (2, 4)]
        )

    def test_without_a_heuristic_routes_are_never_replaced(self):
        # Entering a cell costs the same from every side and h=0 expands nodes in
        # order of g, so the first route found to any cell is already the best.
        for seed, grid in self.random_maps():
            with self.subTest(seed=seed):
                result = astar(grid, grid.start, grid.goal, "Zero (Dijkstra)")
                self.assertEqual(result.path_updates, 0)

    def test_better_heuristic_never_explores_more_than_no_heuristic(self):
        grid = load("2_obstacle_filled.txt")
        guided = astar(grid, grid.start, grid.goal, "Manhattan")
        unguided = astar(grid, grid.start, grid.goal, "Zero (Dijkstra)")
        self.assertLess(guided.nodes_explored, unguided.nodes_explored)
        self.assertEqual(guided.path_cost, unguided.path_cost)


class MapTests(unittest.TestCase):
    def test_text_round_trip(self):
        for path in MAPS.glob("*.txt"):
            with self.subTest(map=path.name):
                grid = GridMap.from_file(path)
                again = GridMap.from_text(grid.to_text())
                self.assertEqual(again.tiles, grid.tiles)
                self.assertEqual((again.start, again.goal), (grid.start, grid.goal))

    def test_neighbours_respect_edges_walls_and_order(self):
        grid = GridMap.from_text("S#.\n..G")
        self.assertEqual(grid.neighbors((0, 0)), [(1, 0)])
        self.assertEqual(grid.neighbors((1, 1)), [(1, 2), (1, 0)])
        grid.set_direction_order("LURD")
        self.assertEqual(grid.neighbors((1, 1)), [(1, 0), (1, 2)])

    def test_start_and_goal_cannot_become_walls(self):
        grid = GridMap.from_text("S.G")
        with self.assertRaises(InvalidInputError):
            grid.set_tile(grid.start, WALL)
        with self.assertRaises(InvalidInputError):
            grid.set_tile(grid.goal, WALL)

    def test_is_valid_path_rejects_bad_paths(self):
        grid = GridMap.from_text("S.#\n..G")
        start, goal = grid.start, grid.goal
        self.assertTrue(grid.is_valid_path([start, (0, 1), (1, 1), goal], start, goal))
        self.assertFalse(grid.is_valid_path([], start, goal))
        self.assertFalse(grid.is_valid_path([(0, 1), (1, 1), goal], start, goal))
        self.assertFalse(grid.is_valid_path([start, (1, 1), goal], start, goal))  # Diagonal.
        self.assertFalse(grid.is_valid_path([start, (0, 1), (0, 2), goal], start, goal))  # Wall.

    def test_mud_costs_more_than_open_ground(self):
        grid = GridMap.from_text("S~G")
        self.assertEqual(grid.path_cost([(0, 0), (0, 1), (0, 2)]), 6)


class ReportingTests(unittest.TestCase):
    def test_comparison_table_uses_measured_values(self):
        grid = load("3_multiple_paths.txt")
        results = compare_all(grid)
        rows = {row[0]: row[1:] for row in comparison_rows(results)}
        self.assertEqual(rows["Path cost"], ["82", "70", "26"])
        self.assertEqual(rows["Path found"], ["Yes", "Yes", "Yes"])
        self.assertEqual(rows["Guarantees shortest path"][1], "No, in general")
        for name, shown in zip(ALGORITHMS, rows["Execution time (ms)"]):
            self.assertGreater(results[name].execution_ms, 0)
            self.assertEqual(shown, f"{results[name].execution_ms:.3f}")

    def test_unreachable_row_values_and_notes(self):
        results = compare_all(load("4_unreachable.txt"))
        rows = {row[0]: row[1:] for row in comparison_rows(results)}
        self.assertEqual(rows["Path cost"], ["-", "-", "-"])
        self.assertIn("No path exists", observations(results)[0])

    def test_notes_name_the_real_winners(self):
        notes = " ".join(observations(compare_all(load("3_multiple_paths.txt"))))
        self.assertIn("Fewest moves: BFS (22)", notes)
        self.assertIn("Lowest cost: A* (26)", notes)

    def test_format_path_shortens_long_paths(self):
        path = [(0, col) for col in range(50)]
        short = format_path(path, limit=4)
        self.assertIn("... 46 more ...", short)
        self.assertTrue(short.startswith("(0,0)"))
        self.assertTrue(short.endswith("(0,49)"))
        self.assertEqual(format_path([]), "(no path)")


class ConsoleTests(unittest.TestCase):
    def run_menu(self, *typed: str) -> str:
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=list(typed)), redirect_stdout(output):
            console.run_console()
        return output.getvalue()

    def test_compare_then_quit(self):
        text = self.run_menu("8", "0")
        self.assertIn("Nodes explored", text)
        self.assertIn("Guarantees shortest path", text)

    def test_run_each_algorithm(self):
        text = self.run_menu("7", "1", "7", "2", "7", "3", "0")
        for name in ALGORITHMS:
            self.assertIn(f"Algorithm:      {name}", text)
        self.assertIn("Heuristic:      Manhattan", text)

    def test_bad_input_keeps_the_menu_running(self):
        text = self.run_menu(
            "banana",                       # Not a menu option.
            "7", "9",                       # Algorithm number out of range.
            "7", "x",                       # Algorithm not a number.
            "5", "1", "0 0",                # Start with one number only.
            "5", "99 99", "0 0",            # Start outside the map.
            "6", "a b",                     # Cell not numeric.
            "3", "no_such_file.txt",        # Missing file.
            "4", "0", "5",                  # Zero rows.
            "0",
        )
        self.assertIn("Please choose an option", text)
        self.assertIn("Choose a number from 1 to 3", text)
        self.assertIn("is outside the map", text)
        self.assertIn("Could not read map file", text)
        self.assertIn("at least one row", text)

    def test_toggle_and_block_every_route(self):
        # Wall off the goal's four neighbours, then confirm no path is reported.
        text = self.run_menu(
            "5", "0 0", "1 1",
            "6", "0 1", "6", "1 0", "6", "1 2", "6", "2 1",
            "7", "1", "0",
        )
        self.assertIn("Goal reached:   No", text)
        self.assertIn("No path exists", text)

    def test_ending_input_quits_cleanly(self):
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=EOFError), redirect_stdout(output):
            console.run_console()

    def test_missing_sample_maps_fall_back_to_a_blank_map(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            sample_maps, "MAPS_DIR", Path(folder)
        ):
            text = self.run_menu("2", "7", "1", "0")
        self.assertIn("nothing to choose from", text)
        self.assertIn("Goal reached:   Yes", text)

    def test_broken_sample_map_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            sample_maps, "MAPS_DIR", Path(folder)
        ):
            (Path(folder) / "1_broken.txt").write_text("not a map", encoding="utf-8")
            (Path(folder) / "2_good.txt").write_text("S.G", encoding="utf-8")
            self.assertEqual(sample_maps.starting_map().cols, 3)

    def test_render_marks_path_and_explored(self):
        grid = GridMap.from_text("S.\n.G")
        drawing = console.render(grid, bfs(grid, grid.start, grid.goal))
        self.assertIn("S" + console.PATH_MARK, drawing)


class CommandLineTests(unittest.TestCase):
    def test_one_shot_run(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main_module.main(["--map", str(MAPS / "1_simple_path.txt"), "--algorithm", "DFS"])
        self.assertEqual(code, 0)
        self.assertIn("Goal reached:   Yes", output.getvalue())

    def test_bad_map_reports_an_error_and_exit_code(self):
        errors = io.StringIO()
        with mock.patch("sys.stderr", errors):
            code = main_module.main(["--map", str(MAPS / "invalid" / "uneven_rows.txt")])
        self.assertEqual(code, 1)
        self.assertIn("same length", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
