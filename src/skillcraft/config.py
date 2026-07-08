"""Per-repo configuration (``.skillcraft.toml``)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from skillcraft.sync import TargetSpec


@dataclass
class RepoConfig:
    canonical: str = "AGENTS.md"
    targets: list[TargetSpec] = field(default_factory=list)


def default_targets() -> list[TargetSpec]:
    return [TargetSpec("skill", Path("SKILL.md")), TargetSpec("claude", Path("CLAUDE.md"))]


def load_config(root: Path) -> RepoConfig:
    """Load ``.skillcraft.toml`` from ``root``; fall back to defaults."""
    cfg = RepoConfig(canonical="AGENTS.md", targets=default_targets())
    file = Path(root) / ".skillcraft.toml"
    if not file.is_file():
        return cfg
    try:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return cfg
    sync = data.get("sync", {})
    if isinstance(sync.get("canonical"), str):
        cfg.canonical = sync["canonical"]
    raw_targets = sync.get("targets")
    if isinstance(raw_targets, list) and raw_targets:
        parsed: list[TargetSpec] = []
        for entry in raw_targets:
            if isinstance(entry, dict) and "format" in entry and "path" in entry:
                parsed.append(TargetSpec(entry["format"], Path(entry["path"])))
        cfg.targets = parsed or default_targets()
    return cfg
