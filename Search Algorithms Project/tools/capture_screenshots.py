"""Open the real window, run searches, and save screenshots to screenshots/.

    python tools/capture_screenshots.py

Needs Pillow (pip install pillow). The program itself does not. The window must
stay visible while this runs, because each picture is taken from the screen.
"""

from __future__ import annotations

import sys
import time
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from gui import SearchApp, enable_high_dpi  # noqa: E402

OUTPUT = PROJECT / "screenshots"


def settle(root: tk.Misc, seconds: float = 0.5) -> None:
    """Let Tk process events and repaint for a moment."""
    finish = time.monotonic() + seconds
    while time.monotonic() < finish:
        root.update()
        time.sleep(0.01)


def capture(window: tk.Misc, name: str) -> None:
    window.lift()
    window.attributes("-topmost", True)
    settle(window)
    box = (
        window.winfo_rootx(),
        window.winfo_rooty(),
        window.winfo_rootx() + window.winfo_width(),
        window.winfo_rooty() + window.winfo_height(),
    )
    ImageGrab.grab(bbox=box, all_screens=True).save(OUTPUT / name)
    window.attributes("-topmost", False)
    print(f"Saved {OUTPUT / name}")


def wait_for_animation(app: SearchApp) -> None:
    while app.animation_id is not None:
        app.root.update()
        time.sleep(0.005)


def choose_map(app: SearchApp, name: str) -> None:
    app.map_choice.set(name)
    app.load_sample_map()
    settle(app.root, 0.2)


def run(app: SearchApp, algorithm: str) -> None:
    app.algorithm_buttons[algorithm].invoke()
    app.run_button.invoke()
    wait_for_animation(app)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    enable_high_dpi()
    root = tk.Tk()
    app = SearchApp(root)
    settle(root)

    app.speed.set("Instant")
    choose_map(app, "Multiple paths")
    for name, file_name in (("BFS", "bfs"), ("DFS", "dfs"), ("A*", "astar")):
        run(app, name)
        capture(root, f"multiple_paths_{file_name}.png")

    choose_map(app, "Unreachable")
    run(app, "A*")
    capture(root, "unreachable.png")

    # Stop part-way through an animation to show the frontier and explored cells.
    choose_map(app, "Obstacle filled")
    app.speed.set("Fast")
    app.algorithm_buttons["A*"].invoke()
    app.run_button.invoke()
    settle(root, 0.3)
    capture(root, "search_in_progress.png")
    wait_for_animation(app)

    app.speed.set("Instant")
    app.compare_button.invoke()
    settle(root)
    app.compare_window.update()
    capture(app.compare_window, "side_by_side.png")

    root.destroy()


if __name__ == "__main__":
    main()
