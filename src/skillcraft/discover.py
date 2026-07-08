"""Discover agent-config files in a directory tree."""

from __future__ import annotations

from pathlib import Path

from skillcraft.plugins.registry import converter_for_path, load_plugins

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


def discover(root: Path) -> list[Path]:
    """Return all files under ``root`` that some converter claims, sorted."""
    load_plugins()
    root = Path(root)
    if root.is_file():
        return [root] if converter_for_path(root) is not None else []
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if converter_for_path(path) is not None:
            found.append(path)
    return sorted(found)
