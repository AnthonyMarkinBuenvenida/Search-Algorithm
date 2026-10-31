"""Tests that drive the real Tkinter window. Skipped if no display is available."""

from __future__ import annotations

import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import sample_maps  # noqa: E402
from gui import SearchApp, cells_between  # noqa: E402
from search import GridMap  # noqa: E402
from search.grid_map import MUD, OPEN, WALL  # noqa: E402


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"no display: {error}")
        self.app = SearchApp(self.root)
        self.app.speed.set("Instant")
        self.root.update()

    def tearDown(self):
        self.app._stop_animation()
        self.root.destroy()

    def choose_map(self, name: str) -> None:
        self.app.map_choice.set(name)
        self.app.load_sample_map()
        self.root.update()

    def pixel(self, cell):
        """A fake mouse event at the middle of a cell."""
        x, y = self.app.view._center(cell)
        return SimpleNamespace(x=x, y=y)

    def table_rows(self) -> dict:
        table = self.app.table
        rows = [table.item(item, "values") for item in table.get_children()]
        return {row[0]: row[1:] for row in rows}

    def test_all_sample_maps_load(self):
        self.assertEqual(len(self.app.maps), 5)
        for name in self.app.maps:
            self.choose_map(name)
            self.assertEqual(self.app.grid, self.app.view.grid)

    def test_run_each_algorithm_fills_results_and_table(self):
        self.choose_map("Multiple paths")
        expected_moves = {"BFS": "22 moves", "DFS": "30 moves", "A*": "26 moves"}
        for name, moves in expected_moves.items():
            with self.subTest(algorithm=name):
                self.app.algorithm_buttons[name].invoke()
                self.app.run_button.invoke()
                self.root.update()
                values = self.app.result_values
                self.assertEqual(values["Algorithm"].get(), name)
                self.assertEqual(values["Goal reached"].get(), "Yes")
                self.assertEqual(values["Path length"].get(), moves)
                self.assertNotEqual(values["Execution time"].get(), "-")
                self.assertEqual(self.table_rows()["Path cost"], ("82", "70", "26"))
                self.assertIn("->", self.app.path_text.get("1.0", "end"))

    def test_explored_and_path_cells_are_drawn_differently(self):
        self.choose_map("Obstacle filled")
        self.app.run_button.invoke()
        self.root.update()
        view = self.app.view
        states = set(view.states.values())
        self.assertIn("visited", states)
        self.assertIn("path", states)
        path_cell = next(c for c, s in view.states.items()
                         if s == "path" and c not in (view.grid.start, view.grid.goal))
        visited_cell = next(c for c, s in view.states.items() if s == "visited")
        fill = view.canvas.itemcget
        self.assertNotEqual(fill(view.items[path_cell], "fill"),
                            fill(view.items[visited_cell], "fill"))

    def test_unreachable_goal_is_reported(self):
        self.choose_map("Unreachable")
        self.app.run_button.invoke()
        self.assertEqual(self.app.result_values["Goal reached"].get(), "No")
        self.assertIn("No path exists", self.app.status.get())
        self.assertEqual(self.table_rows()["Path found"], ("No", "No", "No"))

    def test_start_equals_goal(self):
        self.choose_map("Start equals goal")
        self.app.run_button.invoke()
        self.assertEqual(self.app.result_values["Path length"].get(), "0 moves")
        self.assertEqual(self.app.result_values["Nodes explored"].get(), "1")

    def test_paint_and_erase_cells(self):
        cell = (0, 0)
        for tool, tile in (("wall", WALL), ("mud", MUD), ("erase", OPEN)):
            self.app.tool.set(tool)
            self.app._on_press(self.pixel(cell))
            self.app._on_release(None)
            self.assertEqual(self.app.grid.tile_at(cell), tile)

    def test_drag_paints_a_line_without_gaps(self):
        self.app.tool.set("wall")
        self.app._on_press(self.pixel((0, 0)))
        self.app._on_drag(self.pixel((0, 6)))
        self.app._on_release(None)
        for col in range(7):
            self.assertEqual(self.app.grid.tile_at((0, col)), WALL)

    def test_painting_over_markers_is_ignored(self):
        self.app.tool.set("mud")
        start = self.app.grid.start
        self.app._on_press(self.pixel(start))
        self.app._on_release(None)
        self.assertEqual(self.app.grid.tile_at(start), OPEN)
        self.assertEqual(self.app.grid.start, start)

    def test_drag_marker_to_a_new_cell(self):
        goal = self.app.grid.goal
        self.app._on_press(self.pixel(goal))
        self.app._on_drag(self.pixel((goal[0], goal[1] + 2)))
        self.app._on_release(None)
        self.assertEqual(self.app.grid.goal, (goal[0], goal[1] + 2))

    def test_move_tool_refuses_a_wall(self):
        self.app.grid.set_tile((0, 0), WALL)
        self.app.tool.set("start")
        start = self.app.grid.start
        self.app._on_press(self.pixel((0, 0)))
        self.app._on_release(None)
        self.assertEqual(self.app.grid.start, start)
        self.assertIn("wall", self.app.status.get())

    def test_move_tool_can_stack_goal_on_start(self):
        self.app.tool.set("goal")
        self.app._on_press(self.pixel(self.app.grid.start))
        self.app._on_release(None)
        self.assertEqual(self.app.grid.goal, self.app.grid.start)
        self.app.run_button.invoke()
        self.assertEqual(self.app.result_values["Path length"].get(), "0 moves")

    def test_starts_on_a_blank_map_if_the_samples_are_missing(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            sample_maps, "MAPS_DIR", Path(folder)
        ):
            root = tk.Toplevel(self.root)
            app = SearchApp(root)
            app.speed.set("Instant")
            self.assertEqual((app.grid.rows, app.grid.cols), (15, 25))
            app.load_sample_map()  # Nothing to load: must not fail.
            app.run_button.invoke()
            self.assertEqual(app.result_values["Goal reached"].get(), "Yes")

    def test_largest_map_stays_responsive(self):
        self.app._show_map(GridMap.blank(100, 100))
        self.root.update()
        began = time.perf_counter()
        self.app.run_button.invoke()
        self.root.update()
        self.assertEqual(self.app.result_values["Goal reached"].get(), "Yes")
        self.assertLess(time.perf_counter() - began, 5)

    def test_editing_the_map_clears_stale_results(self):
        self.app.run_button.invoke()
        self.assertTrue(self.table_rows())
        self.app.tool.set("wall")
        self.app._on_press(self.pixel((0, 0)))
        self.app._on_release(None)
        self.assertEqual(self.table_rows(), {})
        self.assertEqual(self.app.result_values["Algorithm"].get(), "-")
        self.assertEqual(self.app.view.states, {})

    def test_clear_search_keeps_the_map_and_reset_restores_it(self):
        original = self.app.grid.to_text()
        self.app.tool.set("wall")
        self.app._on_press(self.pixel((0, 0)))
        self.app._on_release(None)
        self.app.run_button.invoke()

        self.app.clear_button.invoke()
        self.assertEqual(self.app.view.states, {})
        self.assertNotEqual(self.app.grid.to_text(), original)

        self.app.reset_button.invoke()
        self.assertEqual(self.app.grid.to_text(), original)

    def test_bad_map_file_shows_an_error_and_keeps_the_current_map(self):
        before = self.app.grid
        self.app.load_map_file(str(PROJECT / "maps" / "invalid" / "uneven_rows.txt"))
        self.assertIn("Could not load", self.app.status.get())
        self.assertIs(self.app.grid, before)

    def test_load_map_file_is_used_by_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "small.txt"
            path.write_text("S.G\n", encoding="utf-8")
            self.app.load_map_file(str(path))
        self.assertEqual(self.app.grid.cols, 3)
        self.app.reset_button.invoke()
        self.assertEqual(self.app.grid.cols, 3)

    def test_animation_finishes_and_can_be_interrupted(self):
        self.choose_map("Multiple paths")
        self.app.speed.set("Fast")
        self.app.run_button.invoke()
        self.assertIsNotNone(self.app.animation_id)
        self.app.clear_button.invoke()
        self.assertIsNone(self.app.animation_id)
        self.assertEqual(self.app.view.states, {})

        self.app.run_button.invoke()
        for _ in range(4000):
            if self.app.animation_id is None:
                break
            self.root.update()
            self.root.after(1)
        self.assertIsNone(self.app.animation_id)
        self.assertEqual(self.app.result_values["Goal reached"].get(), "Yes")
        self.assertEqual(self.app.run_button.instate(["disabled"]), False)

    def test_side_by_side_window(self):
        self.choose_map("Multiple paths")
        self.app.compare_button.invoke()
        self.root.update()
        self.assertIsNotNone(self.app.compare_window)
        self.assertEqual(self.table_rows()["Path cost"], ("82", "70", "26"))
        self.app._on_comparison_closed()
        self.assertIsNone(self.app.compare_window)

    def test_neighbour_order_setting_is_used(self):
        self.app.algorithm_buttons["DFS"].invoke()
        self.app.run_button.invoke()
        first = self.app.result_values["Path length"].get()
        self.app.neighbor_order.set("Down, Right, Up, Left")
        self.app.run_button.invoke()
        self.assertNotEqual(self.app.result_values["Path length"].get(), first)

    def test_heuristic_setting_is_used(self):
        self.app.heuristic.set("Zero (Dijkstra)")
        self.app.run_button.invoke()
        self.assertEqual(self.app.result_values["Heuristic"].get(), "Zero (Dijkstra)")

    def test_click_outside_the_map_does_nothing(self):
        before = self.app.grid.to_text()
        self.app.view.canvas.update()
        self.app._on_press(SimpleNamespace(x=-50, y=-50))
        self.app._on_drag(SimpleNamespace(x=-50, y=-50))
        self.app._on_release(None)
        self.assertEqual(self.app.grid.to_text(), before)


class HelperTests(unittest.TestCase):
    def test_cells_between(self):
        self.assertEqual(cells_between((0, 0), (0, 3)), [(0, 1), (0, 2), (0, 3)])
        self.assertEqual(cells_between((2, 2), (0, 0)), [(1, 1), (0, 0)])


if __name__ == "__main__":
    unittest.main()
