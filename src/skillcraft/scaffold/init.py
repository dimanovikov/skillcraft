"""Scaffolding for `skillcraft init`."""

from __future__ import annotations

import json
from pathlib import Path


def _agents_template(name: str) -> str:
    """Render a minimal canonical AGENTS.md carrying the chosen skill name."""
    meta = json.dumps({"name": name, "description": "Describe what this skill does."})
    return f"""\
<!-- skillcraft:meta {meta} -->

# {name}

Describe your project / skill instructions here.

## Build

`npm test`
"""


_CONFIG_TEMPLATE = """\
# skillcraft configuration — https://github.com/topics/skillcraft
[sync]
canonical = "AGENTS.md"

[[sync.targets]]
format = "skill"
path = "SKILL.md"

[[sync.targets]]
format = "claude"
path = "CLAUDE.md"
"""


def init_repo(root: Path, name: str = "my-skill") -> list[Path]:
    """Create a minimal canonical AGENTS.md and .skillcraft.toml if absent."""
    root = Path(root)
    written: list[Path] = []
    agents = root / "AGENTS.md"
    config = root / ".skillcraft.toml"
    if not agents.exists():
        agents.write_text(_agents_template(name), encoding="utf-8")
        written.append(agents)
    if not config.exists():
        config.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
        written.append(config)
    return written
