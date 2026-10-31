"""Tkinter interface: edit a map, watch a search run, and compare the results."""

from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

from sample_maps import sample_maps, starting_map
from search import ALGORITHMS, GridMap, InvalidInputError, SearchResult, compare_all
from search.grid_map import MUD, OPEN, WALL, Cell
from search.heuristics import DEFAULT_HEURISTIC, HEURISTICS
from search.result import SearchStep
from search.runner import comparison_rows, format_path, observations

COLORS = {
    "window": "#eef0f3",
    "panel": "#ffffff",
    "text": "#1f2933",
    "muted": "#5f6b7a",
    "error": "#b42318",
    "grid_line": "#d9dee5",
    "open": "#ffffff",
    "wall": "#2d3640",
    "mud": "#c9a77c",
    "visited": "#b9d6f6",
    "visited_mud": "#8db0cf",
    "frontier": "#fce7a6",
    "frontier_mud": "#e3c777",
    "current": "#f28c28",
    "path": "#7c3aed",
    "path_mud": "#5521b5",
    "path_line": "#ffffff",
    "start": "#15803d",
    "goal": "#c81e1e",
}

# Milliseconds between animation frames. Zero skips the animation.
SPEEDS = {"Slow": 120, "Normal": 35, "Fast": 8, "Instant": 0}

NEIGHBOR_ORDERS = {
    "Up, Right, Down, Left": "URDL",
    "Right, Down, Left, Up": "RDLU",
    "Down, Left, Up, Right": "DLUR",
    "Left, Up, Right, Down": "LURD",
    "Down, Right, Up, Left": "DRUL",
}

TOOLS = [
    ("Wall", "wall"),
    ("Mud (cost 5)", "mud"),
    ("Erase", "erase"),
    ("Move start", "start"),
    ("Move goal", "goal"),
]
TOOL_TILES = {"wall": WALL, "mud": MUD, "erase": OPEN}

ALGORITHM_NOTES = {
    "BFS": (
        "Uses a FIFO queue, so it spreads out one move at a time. Finds the path "
        "with the fewest moves, but ignores terrain cost."
    ),
    "DFS": (
        "Uses a LIFO stack, so it follows one branch until it is stuck, then "
        "backtracks. It stops at the first route it finds, which need not be short."
    ),
    "A*": (
        "Uses a priority queue ordered by f(n) = g(n) + h(n): cost so far plus "
        "estimated cost left. Finds the cheapest path when h never overestimates."
    ),
}

LEGEND = [
    ("Start", "start"),
    ("Goal", "goal"),
    ("Wall", "wall"),
    ("Mud", "mud"),
    ("Frontier", "frontier"),
    ("Explored", "visited"),
    ("Final path", "path"),
]


def enable_high_dpi() -> None:
    """Ask Windows for sharp text on scaled displays. Harmless if unsupported."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


class GridView:
    """Draws a GridMap on a Canvas, with search progress painted on top."""

    def __init__(self, parent: tk.Widget, grid: GridMap) -> None:
        self.canvas = tk.Canvas(parent, bg=COLORS["panel"], highlightthickness=0)
        self.grid = grid
        self.states: dict[Cell, str] = {}  # "frontier", "visited", "current" or "path"
        self.current: Cell | None = None
        self.path: list[Cell] = []
        self.items: dict[Cell, int] = {}
        self.cell_size = 1
        self.origin = (0, 0)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

    def set_grid(self, grid: GridMap) -> None:
        self.grid = grid
        self.clear_search()

    def clear_search(self) -> None:
        self.states.clear()
        self.current = None
        self.path = []
        self.redraw()

    def cell_at(self, x: int, y: int) -> Cell | None:
        """The cell under a canvas position, or None if outside the map."""
        col = (x - self.origin[0]) // self.cell_size
        row = (y - self.origin[1]) // self.cell_size
        if 0 <= row < self.grid.rows and 0 <= col < self.grid.cols:
            return row, col
        return None

    def _fill(self, cell: Cell) -> str:
        if cell == self.grid.start:
            return COLORS["start"]
        if cell == self.grid.goal:
            return COLORS["goal"]
        tile = self.grid.tile_at(cell)
        if tile == WALL:
            return COLORS["wall"]
        state = self.states.get(cell)
        if state == "current":
            return COLORS["current"]
        if state:
            return COLORS[state + "_mud"] if tile == MUD else COLORS[state]
        return COLORS["mud"] if tile == MUD else COLORS["open"]

    def _center(self, cell: Cell) -> tuple[int, int]:
        half = self.cell_size // 2
        return (
            self.origin[0] + cell[1] * self.cell_size + half,
            self.origin[1] + cell[0] * self.cell_size + half,
        )

    def redraw(self) -> None:
        """Rebuild the whole drawing, e.g. after a resize or a new map."""
        canvas = self.canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        self.cell_size = max(4, min(width // self.grid.cols, height // self.grid.rows))
        self.origin = (
            (width - self.cell_size * self.grid.cols) // 2,
            (height - self.cell_size * self.grid.rows) // 2,
        )

        canvas.delete("all")
        self.items.clear()
        for row in range(self.grid.rows):
            for col in range(self.grid.cols):
                x = self.origin[0] + col * self.cell_size
                y = self.origin[1] + row * self.cell_size
                self.items[(row, col)] = canvas.create_rectangle(
                    x, y, x + self.cell_size, y + self.cell_size,
                    fill=self._fill((row, col)), outline=COLORS["grid_line"],
                )
        self._draw_path_line()
        self._draw_markers()

    def _draw_path_line(self) -> None:
        # The line skips the two end cells so it does not cross their letters.
        inner_path = self.path[1:-1]
        if len(inner_path) > 1:
            points = [value for cell in inner_path for value in self._center(cell)]
            self.canvas.create_line(*points, fill=COLORS["path_line"], width=2)

    def _draw_markers(self) -> None:
        font = ("Segoe UI", max(7, self.cell_size // 2), "bold")
        if self.grid.start == self.grid.goal:
            marks = [(self.grid.start, "S=G")]
        else:
            marks = [(self.grid.start, "S"), (self.grid.goal, "G")]
        for cell, text in marks:
            x, y = self._center(cell)
            self.canvas.create_text(
                x, y, text=text, fill="#ffffff", font=font, tags="marker"
            )

    def update_cell(self, cell: Cell) -> None:
        """Recolour one cell. Before the first draw there is nothing to recolour."""
        if cell in self.items:
            self.canvas.itemconfigure(self.items[cell], fill=self._fill(cell))

    def set_state(self, cell: Cell, state: str) -> None:
        self.states[cell] = state
        self.update_cell(cell)

    def _finish_current(self) -> None:
        if self.current is not None:
            self.set_state(self.current, "visited")
            self.current = None

    def apply_step(self, step: SearchStep) -> None:
        """Show one expansion: the node is now explored, its neighbours wait."""
        self._finish_current()
        for cell in step.discovered:
            if self.states.get(cell) != "visited":
                self.set_state(cell, "frontier")
        self.set_state(step.cell, "current")
        self.current = step.cell

    def show_final(self, result: SearchResult) -> None:
        """Show a finished search: all explored nodes, then the path on top."""
        for step in result.steps:
            self.apply_step(step)
        self.show_path(result)

    def show_path(self, result: SearchResult) -> None:
        self._finish_current()
        for cell in result.path:
            self.set_state(cell, "path")
        self.path = result.path
        self._draw_path_line()


class SearchApp:
    """The main window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.maps = sample_maps()
        self.grid = starting_map()
        self.original_map = self.grid.to_text()

        self.animation_id: str | None = None
        self.dragging: str | None = None  # "start" or "goal" while moving a marker.
        self.last_cell: Cell | None = None
        self.compare_window: tk.Toplevel | None = None

        self.map_choice = tk.StringVar(value=next(iter(self.maps), ""))
        self.algorithm = tk.StringVar(value="A*")
        self.heuristic = tk.StringVar(value=DEFAULT_HEURISTIC)
        self.neighbor_order = tk.StringVar(value=next(iter(NEIGHBOR_ORDERS)))
        self.speed = tk.StringVar(value="Normal")
        self.tool = tk.StringVar(value="wall")
        self.status = tk.StringVar()
        self.result_values = {
            label: tk.StringVar(value="-")
            for label in (
                "Algorithm", "Goal reached", "Nodes explored", "Path length",
                "Path cost", "Execution time", "Heuristic", "Route updates",
            )
        }

        self._build_window()
        self._on_algorithm_change()
        self._set_status("Choose an algorithm and press Run search.")

    # ------------------------------------------------------------------
    # Window layout
    # ------------------------------------------------------------------

    def _build_window(self) -> None:
        self.root.title("BFS, DFS and A* Search")
        self.root.configure(bg=COLORS["window"])

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=COLORS["window"], foreground=COLORS["text"],
                        font=("Segoe UI", 10))
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Panel.TLabel", background=COLORS["panel"])
        style.configure("Panel.TRadiobutton", background=COLORS["panel"])
        style.configure("Heading.TLabel", background=COLORS["panel"],
                        font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background=COLORS["panel"],
                        foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=COLORS["path"], foreground="#ffffff",
                        font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Accent.TButton",
                  background=[("disabled", "#b9b2cf"), ("active", COLORS["path_mud"])],
                  foreground=[("disabled", "#ffffff")])
        style.configure("Treeview", rowheight=26, background=COLORS["panel"],
                        fieldbackground=COLORS["panel"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        map_area = ttk.Frame(self.root, padding=(12, 12, 6, 6))
        map_area.grid(row=0, column=0, sticky="nsew")
        map_area.columnconfigure(0, weight=1)
        map_area.rowconfigure(0, weight=1)

        self.view = GridView(map_area, self.grid)
        self.view.canvas.grid(row=0, column=0, sticky="nsew")
        self.view.canvas.bind("<ButtonPress-1>", self._on_press)
        self.view.canvas.bind("<B1-Motion>", self._on_drag)
        self.view.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._build_legend(map_area).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.status_label = ttk.Label(map_area, textvariable=self.status, wraplength=880)
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self._build_controls(self.root).grid(
            row=0, column=1, sticky="nsew", padx=(6, 12), pady=(12, 6))

        bottom = ttk.Frame(self.root, padding=(12, 6, 12, 12))
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self._build_comparison(bottom).grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._build_results(bottom).grid(row=0, column=1, sticky="nsew")

        # Open tall enough to show every control, but never taller than the screen.
        self.root.update_idletasks()
        needed = self.root.winfo_reqheight()
        height = min(max(860, needed), self.root.winfo_screenheight() - 80)
        self.root.geometry(f"1280x{height}")
        self.root.minsize(1060, min(needed, height))

    def _build_legend(self, parent: tk.Widget) -> ttk.Frame:
        legend = ttk.Frame(parent)
        for label, color in LEGEND:
            swatch = tk.Frame(legend, width=14, height=14, bg=COLORS[color],
                              highlightbackground=COLORS["grid_line"], highlightthickness=1)
            swatch.pack(side="left", padx=(0, 4))
            ttk.Label(legend, text=label).pack(side="left", padx=(0, 14))
        return legend

    def _build_controls(self, parent: tk.Widget) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=12)

        def heading(text: str) -> None:
            ttk.Label(panel, text=text, style="Heading.TLabel").pack(anchor="w", pady=(8, 2))

        def dropdown(variable: tk.StringVar, values: list[str]) -> ttk.Combobox:
            box = ttk.Combobox(panel, textvariable=variable, values=values,
                               state="readonly", width=30)
            box.pack(fill="x")
            return box

        ttk.Label(panel, text="Algorithm", style="Heading.TLabel").pack(anchor="w")
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        self.algorithm_buttons = {}
        for name in ALGORITHMS:
            button = ttk.Radiobutton(row, text=name, value=name, variable=self.algorithm,
                                     style="Panel.TRadiobutton",
                                     command=self._on_algorithm_change)
            button.pack(side="left", padx=(0, 14))
            self.algorithm_buttons[name] = button
        self.algorithm_note = ttk.Label(panel, style="Muted.TLabel", wraplength=300)
        self.algorithm_note.pack(anchor="w", pady=(4, 0))

        heading("A* heuristic")
        dropdown(self.heuristic, list(HEURISTICS))
        heading("Neighbour order")
        dropdown(self.neighbor_order, list(NEIGHBOR_ORDERS))
        heading("Animation speed")
        dropdown(self.speed, list(SPEEDS))

        self.run_button = ttk.Button(panel, text="Run search", style="Accent.TButton",
                                     command=self.run_selected)
        self.run_button.pack(fill="x", pady=(12, 4))
        self.compare_button = ttk.Button(panel, text="Compare side by side",
                                         command=self.open_comparison)
        self.compare_button.pack(fill="x", pady=(0, 4))
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        self.clear_button = ttk.Button(row, text="Clear search", command=self.clear_search)
        self.clear_button.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.reset_button = ttk.Button(row, text="Reset map", command=self.reset_map)
        self.reset_button.pack(side="left", expand=True, fill="x", padx=(2, 0))

        heading("Map")
        box = dropdown(self.map_choice, list(self.maps))
        box.bind("<<ComboboxSelected>>", lambda _event: self.load_sample_map())
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x", pady=(4, 0))
        for text, command in (("Random", self.random_map), ("Load...", self.load_map_file),
                              ("Save...", self.save_map_file)):
            ttk.Button(row, text=text, command=command, width=8).pack(
                side="left", expand=True, fill="x", padx=1)

        heading("Click or drag on the map to place")
        row = None
        for index, (label, value) in enumerate(TOOLS):
            if index % 3 == 0:
                row = ttk.Frame(panel, style="Panel.TFrame")
                row.pack(fill="x")
            ttk.Radiobutton(row, text=label, value=value, variable=self.tool, width=11,
                            style="Panel.TRadiobutton").pack(side="left")
        return panel

    def _build_results(self, parent: tk.Widget) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        ttk.Label(panel, text="Results", style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        for index, (label, variable) in enumerate(self.result_values.items(), start=1):
            ttk.Label(panel, text=label, style="Muted.TLabel").grid(
                row=index, column=0, sticky="w", padx=(0, 16))
            ttk.Label(panel, textvariable=variable, style="Panel.TLabel", width=14).grid(
                row=index, column=1, sticky="w")

        ttk.Label(panel, text="Path found", style="Heading.TLabel").grid(
            row=0, column=2, sticky="w", padx=(12, 0), pady=(0, 4))
        self.path_text = tk.Text(panel, height=8, width=42, wrap="word", relief="flat",
                                 bg=COLORS["window"], font=("Consolas", 9), state="disabled")
        self.path_text.grid(row=1, column=2, rowspan=len(self.result_values), sticky="nsew",
                            padx=(12, 0))
        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.path_text.yview)
        scroll.grid(row=1, column=3, rowspan=len(self.result_values), sticky="ns")
        self.path_text.configure(yscrollcommand=scroll.set)
        return panel

    def _build_comparison(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        frame.columnconfigure(0, weight=1)
        columns = ("metric", *ALGORITHMS)
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=6,
                                  selectmode="none")
        self.table.heading("metric", text="Metric", anchor="w")
        self.table.column("metric", width=160, anchor="w")
        for name, width in zip(ALGORITHMS, (165, 110, 205)):
            self.table.heading(name, text=name, anchor="w")
            self.table.column(name, width=width, anchor="w")
        self.table.grid(row=0, column=0, sticky="ew")

        # A fixed three-line area, so the map does not jump when the notes appear.
        line_height = tkfont.Font(font=("Segoe UI", 9)).metrics("linespace")
        notes_area = ttk.Frame(frame, style="Panel.TFrame", height=3 * line_height)
        notes_area.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        notes_area.pack_propagate(False)
        self.notes = ttk.Label(notes_area, style="Muted.TLabel")
        self.notes.pack(fill="x")
        notes_area.bind(
            "<Configure>", lambda event: self.notes.configure(wraplength=event.width)
        )
        return frame

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str, error: bool = False) -> None:
        self.status.set(message)
        self.status_label.configure(
            foreground=COLORS["error"] if error else COLORS["text"]
        )

    def _on_algorithm_change(self) -> None:
        name = self.algorithm.get()
        self.algorithm_note.configure(text=ALGORITHM_NOTES[name])

    def _apply_neighbor_order(self) -> None:
        self.grid.set_direction_order(NEIGHBOR_ORDERS[self.neighbor_order.get()])

    def _stop_animation(self) -> None:
        if self.animation_id is not None:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None
        self.run_button.state(["!disabled"])
        self.compare_button.state(["!disabled"])

    def _clear_results(self) -> None:
        for variable in self.result_values.values():
            variable.set("-")
        self._set_path_text("")
        self.table.delete(*self.table.get_children())
        self.notes.configure(text="")

    def _close_comparison(self) -> None:
        if self.compare_window is not None:
            self.compare_window.destroy()
            self.compare_window = None

    def _set_path_text(self, text: str) -> None:
        self.path_text.configure(state="normal")
        self.path_text.delete("1.0", "end")
        self.path_text.insert("1.0", text)
        self.path_text.configure(state="disabled")

    def _invalidate_search(self) -> None:
        """The map changed, so anything on screen about old searches is stale."""
        self._stop_animation()
        self._close_comparison()
        self._clear_results()
        if self.view.states:
            self.view.clear_search()

    def _show_map(self, grid: GridMap, source_text: str | None = None) -> None:
        self.grid = grid
        self.original_map = source_text if source_text else grid.to_text()
        self._invalidate_search()
        self.view.set_grid(grid)

    # ------------------------------------------------------------------
    # Running searches
    # ------------------------------------------------------------------

    def _compare(self) -> dict[str, SearchResult] | None:
        """Run all three algorithms. Reports bad input and returns None."""
        self._invalidate_search()
        try:
            self._apply_neighbor_order()
            return compare_all(self.grid, heuristic=self.heuristic.get())
        except InvalidInputError as error:
            self._set_status(f"Error: {error}", error=True)
            return None

    def run_selected(self) -> None:
        """Animate the chosen algorithm, then show the full comparison."""
        results = self._compare()
        if results is None:
            return
        result = results[self.algorithm.get()]

        def finished() -> None:
            self._show_results(result, results)

        self._set_status(f"Running {result.algorithm}...")
        self._play([(self.view, result)], finished, narrate=True)

    def open_comparison(self) -> None:
        """Replay all three algorithms at once, each on its own copy of the map."""
        results = self._compare()
        if results is None:
            return

        window = tk.Toplevel(self.root)
        window.title("Side-by-side comparison")
        window.geometry("1300x520")
        window.configure(bg=COLORS["window"])
        window.protocol("WM_DELETE_WINDOW", self._on_comparison_closed)
        self.compare_window = window

        pairs = []
        captions = []
        for index, (name, result) in enumerate(results.items()):
            window.columnconfigure(index, weight=1, uniform="view")
            frame = ttk.Frame(window, padding=8)
            frame.grid(row=0, column=index, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            ttk.Label(frame, text=name, font=("Segoe UI", 12, "bold")).grid(
                row=0, column=0, sticky="w")
            view = GridView(frame, self.grid.copy())
            view.canvas.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
            caption = ttk.Label(frame, text="Searching...")
            caption.grid(row=2, column=0, sticky="w")
            pairs.append((view, result))
            captions.append((caption, result))
        window.rowconfigure(0, weight=1)
        window.update_idletasks()
        for view, _result in pairs:
            view.redraw()

        def finished() -> None:
            for caption, result in captions:
                length = result.path_length if result.found else "no path"
                caption.configure(
                    text=f"Explored {result.nodes_explored}   Moves {length}   "
                         f"Cost {result.path_cost if result.found else '-'}"
                )
            self._show_results(results[self.algorithm.get()], results)

        self._set_status("Comparing all three algorithms on the same map...")
        self._play(pairs, finished)

    def _on_comparison_closed(self) -> None:
        self._stop_animation()
        self._close_comparison()

    def _play(self, pairs, finished, narrate: bool = False) -> None:
        """Replay searches on their views, then call `finished`.

        `pairs` is a list of (GridView, SearchResult). With `narrate`, the status
        line follows the first search step by step.
        """
        delay = SPEEDS[self.speed.get()]
        if delay == 0:
            for view, result in pairs:
                view.show_final(result)
            finished()
            return

        self.run_button.state(["disabled"])
        self.compare_button.state(["disabled"])
        total = max(len(result.steps) for _view, result in pairs)
        index = 0

        def tick() -> None:
            nonlocal index
            if index >= total:
                self.animation_id = None
                self.run_button.state(["!disabled"])
                self.compare_button.state(["!disabled"])
                for view, result in pairs:
                    view.show_path(result)
                finished()
                return
            for view, result in pairs:
                if index < len(result.steps):
                    view.apply_step(result.steps[index])
                elif index == len(result.steps):
                    view.show_path(result)  # This search finished first.
            if narrate:
                self._narrate(pairs[0][1], index)
            index += 1
            self.animation_id = self.root.after(delay, tick)

        tick()

    def _narrate(self, result: SearchResult, index: int) -> None:
        step = result.steps[index]
        text = f"Step {index + 1}: expanding {step.cell}, frontier size {step.frontier_size}"
        if step.detail:
            text += f", {step.detail}"
        self._set_status(text)

    def _show_results(self, result: SearchResult, results: dict[str, SearchResult]) -> None:
        values = self.result_values
        values["Algorithm"].set(result.algorithm)
        values["Goal reached"].set("Yes" if result.found else "No")
        values["Nodes explored"].set(str(result.nodes_explored))
        values["Path length"].set(f"{result.path_length} moves" if result.found else "-")
        values["Path cost"].set(str(result.path_cost) if result.found else "-")
        values["Execution time"].set(f"{result.execution_ms:.3f} ms")
        is_astar = result.algorithm == "A*"
        values["Heuristic"].set(result.heuristic if is_astar else "Not used")
        values["Route updates"].set(str(result.path_updates) if is_astar else "Not used")
        self._set_path_text(format_path(result.path))

        self.table.delete(*self.table.get_children())
        for row in comparison_rows(results):
            self.table.insert("", "end", values=row)
        self.notes.configure(text=" ".join(observations(results)))
        self._set_status(f"{result.algorithm}: {result.message}", error=not result.found)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def clear_search(self) -> None:
        self._invalidate_search()
        self._set_status("Search cleared. The map is unchanged.")

    def reset_map(self) -> None:
        self._show_map(GridMap.from_text(self.original_map), self.original_map)
        self._set_status("Map reset to how it was loaded.")

    def _open_map(self, path, label: str) -> None:
        try:
            self._show_map(GridMap.from_file(path))
        except InvalidInputError as error:
            self._set_status(f"Could not load that map. {error}", error=True)
        else:
            self._set_status(f"Loaded {label}.")

    def load_sample_map(self) -> None:
        name = self.map_choice.get()
        if name in self.maps:
            self._open_map(self.maps[name], f"sample map: {name}")

    def random_map(self) -> None:
        self._show_map(GridMap.random(18, 30))
        self._set_status("Random map. Walls may happen to block the goal.")

    def load_map_file(self, path: str | None = None) -> None:
        path = path or filedialog.askopenfilename(
            title="Load map", filetypes=[("Map files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self._open_map(path, path)

    def save_map_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save map", defaultextension=".txt", filetypes=[("Map files", "*.txt")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.grid.to_text())
        except OSError as error:
            self._set_status(f"Could not save the map. {error}", error=True)
        else:
            self._set_status(f"Saved {path}.")

    # ------------------------------------------------------------------
    # Editing the map with the mouse
    # ------------------------------------------------------------------

    def _on_press(self, event) -> None:
        cell = self.view.cell_at(event.x, event.y)
        if cell is None:
            return
        self.last_cell = cell
        tool = self.tool.get()
        # With a paint tool selected, pressing a marker picks it up instead.
        if tool in ("start", "goal"):
            self.dragging = tool
        elif cell == self.grid.start:
            self.dragging = "start"
        elif cell == self.grid.goal:
            self.dragging = "goal"
        self._edit_cell(cell)

    def _on_drag(self, event) -> None:
        cell = self.view.cell_at(event.x, event.y)
        if cell is None or self.last_cell is None or cell == self.last_cell:
            return
        for between in cells_between(self.last_cell, cell):
            self._edit_cell(between)
        self.last_cell = cell

    def _on_release(self, _event) -> None:
        self.dragging = None
        self.last_cell = None

    def _edit_cell(self, cell: Cell) -> None:
        if self.dragging:
            self._move_marker(cell)
            return
        if cell in (self.grid.start, self.grid.goal):
            return
        tile = TOOL_TILES[self.tool.get()]
        if self.grid.tile_at(cell) != tile:
            self.grid.set_tile(cell, tile)
            self._invalidate_search()
            self.view.update_cell(cell)

    def _move_marker(self, cell: Cell) -> None:
        marker = self.dragging
        if cell == getattr(self.grid, marker):
            return
        try:
            if marker == "start":
                self.grid.set_start(cell)
            else:
                self.grid.set_goal(cell)
        except InvalidInputError as error:
            self._set_status(f"Error: {error}", error=True)
            return
        self._invalidate_search()
        self.view.redraw()


def cells_between(first: Cell, last: Cell) -> list[Cell]:
    """Cells on the line after `first` up to `last`, so fast drags leave no gaps."""
    count = max(abs(last[0] - first[0]), abs(last[1] - first[1]))
    return [
        (
            first[0] + round((last[0] - first[0]) * step / count),
            first[1] + round((last[1] - first[1]) * step / count),
        )
        for step in range(1, count + 1)
    ]


def run_gui() -> None:
    enable_high_dpi()
    root = tk.Tk()
    SearchApp(root)
    root.mainloop()
