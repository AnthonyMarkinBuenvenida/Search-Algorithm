"""Finds the sample maps in the maps folder."""

from __future__ import annotations

from pathlib import Path

from search import GridMap, InvalidInputError

MAPS_DIR = Path(__file__).parent / "maps"


def sample_maps() -> dict[str, Path]:
    """Sample maps by display name: 1_simple_path.txt becomes "Simple path"."""
    maps = {}
    for path in sorted(MAPS_DIR.glob("*.txt")):
        title = path.stem.split("_", 1)[-1].replace("_", " ")
        maps[title.capitalize()] = path
    return maps


def starting_map() -> GridMap:
    """The first usable sample map, or a blank map if none can be loaded."""
    for path in sample_maps().values():
        try:
            return GridMap.from_file(path)
        except InvalidInputError:
            continue
    return GridMap.blank(15, 25)
