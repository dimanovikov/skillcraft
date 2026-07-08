"""Lint runner: parse each file, run the applicable rules, collect diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from skillcraft.ir import Diagnostic
from skillcraft.plugins.api import Rule
from skillcraft.plugins.registry import all_rules, converter_for_path, load_plugins


def lint_path(path: Path, rules: Iterable[Rule] | None = None) -> list[Diagnostic]:
    """Lint a single file. Returns diagnostics (empty if the format is unknown)."""
    load_plugins()
    if not path.is_file():
        return []
    converter = converter_for_path(path)
    if converter is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    doc = converter.parse(path, text)
    diags: list[Diagnostic] = []
    for rule in rules if rules is not None else all_rules():
        if rule.formats and doc.meta.doc_type not in rule.formats:
            continue
        diags.extend(rule.check(doc))
    return diags


def lint_paths(paths: Iterable[Path], rules: Iterable[Rule] | None = None) -> list[Diagnostic]:
    """Lint many files; diagnostics sorted deterministically by (file, line, rule)."""
    diags: list[Diagnostic] = []
    for path in paths:
        diags.extend(lint_path(Path(path), rules))
    return sorted(diags, key=lambda d: (d.file, d.line or 0, d.rule_id))
