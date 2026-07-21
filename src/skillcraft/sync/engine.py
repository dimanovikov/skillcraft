"""Sync engine.

Parses the canonical ``AGENTS.md`` into a :class:`ConfigDoc`, renders each
target format, and writes a *managed* file prefixed with a
``<!-- skillcraft:managed-source path=… -->`` marker. Drift is detected by
comparing the on-disk target (marker stripped) against a fresh render — a
content comparison that catches edits in *both* directions (canonical changes
and target-side hand-edits alike). Line endings are stable across platforms
because ``.gitattributes`` enforces ``eol=lf``.

Modes:
* write (default) — regenerate managed targets; skip unmanaged ones.
* ``--check``   — report drift; never write.
* ``--diff``    — emit unified diffs for drifted targets.
* ``--adopt``   — force-manage a target (overwrite from canonical).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from skillcraft.ir import ConfigDoc
from skillcraft.markers import managed_marker, parse_managed, strip_managed
from skillcraft.plugins.registry import get_converter, load_plugins


@dataclass
class TargetSpec:
    format_id: str
    path: Path


@dataclass
class SyncResult:
    written: list[Path] = field(default_factory=list)
    drifted: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)
    unmanaged: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # human-readable reasons
    diffs: dict[Path, str] = field(default_factory=dict)

    @property
    def has_drift(self) -> bool:
        return bool(self.drifted or self.missing)


def render_target(canonical_doc: ConfigDoc, target_format_id: str) -> str | None:
    """Render the canonical doc into a target format, or None if it can't be built."""
    load_plugins()
    converter = get_converter(target_format_id)
    if converter is None:
        return None
    if target_format_id == "skill" and not (
        canonical_doc.meta.name and canonical_doc.meta.description
    ):
        # A valid SKILL.md needs name + description; skip if the canonical lacks them.
        return None
    return converter.render(canonical_doc)


def _managed_text(canonical_rel: str, content: str) -> str:
    marker = managed_marker(canonical_rel)
    return f"{marker}\n\n{content.lstrip(chr(10))}"


def _write_managed(target: Path, canonical_rel: str, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_managed_text(canonical_rel, content), encoding="utf-8")


def _check_target(target: Path, canonical_rel: str, content: str) -> str:
    if not target.exists():
        return "missing"
    existing = target.read_text(encoding="utf-8")
    info = parse_managed(existing)
    if info is None:
        return "unmanaged"
    if info.get("path") != canonical_rel:
        return "wrong-source"
    # Drift = the on-disk content (minus marker) differs from a fresh render.
    # Content comparison catches BOTH canonical changes and target-side edits.
    actual = strip_managed(existing).lstrip("\n")
    expected = content.lstrip("\n")
    if actual != expected:
        return "drifted"
    return "ok"


def _unified_diff(actual: str, expected: str, target: Path) -> str:
    return "\n".join(
        difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=f"{target} (on disk)",
            tofile=f"{target} (regenerated)",
            lineterm="",
        )
    )


def run_sync(
    canonical: Path,
    targets: list[TargetSpec],
    *,
    check: bool = False,
    diff: bool = False,
) -> SyncResult:
    """Sync the canonical source to all targets. See module docstring for modes."""
    load_plugins()
    result = SyncResult()
    if not canonical.is_file():
        result.skipped.append(f"canonical source not found: {canonical}")
        return result

    agents = get_converter("agents")
    if agents is None:
        result.skipped.append("no agents converter registered")
        return result
    canonical_doc = agents.parse(canonical, canonical.read_text(encoding="utf-8"))
    canonical_rel = canonical.name

    for spec in targets:
        content = render_target(canonical_doc, spec.format_id)
        if content is None:
            result.skipped.append(
                f"{spec.path}: cannot generate '{spec.format_id}' "
                "(canonical missing required metadata, e.g. skillcraft:meta name/description)"
            )
            continue

        status = _check_target(spec.path, canonical_rel, content)

        if diff and spec.path.exists():
            actual = strip_managed(spec.path.read_text(encoding="utf-8")).lstrip("\n")
            expected = content.lstrip("\n")
            if actual != expected:
                result.diffs[spec.path] = _unified_diff(actual, expected, spec.path)

        if status == "ok":
            result.unchanged.append(spec.path)
        elif status in ("unmanaged", "wrong-source"):
            result.unmanaged.append(spec.path)
        else:  # drifted | missing
            if check:
                result.drifted.append(spec.path)
            else:
                _write_managed(spec.path, canonical_rel, content)
                result.written.append(spec.path)
    return result


def adopt_target(canonical: Path, spec: TargetSpec) -> SyncResult:
    """Force-manage a target: regenerate from canonical and write the marker."""
    load_plugins()
    result = SyncResult()
    agents = get_converter("agents")
    canonical_doc = agents.parse(canonical, canonical.read_text(encoding="utf-8"))
    content = render_target(canonical_doc, spec.format_id)
    if content is None:
        result.skipped.append(f"{spec.path}: cannot generate '{spec.format_id}' from canonical")
        return result
    _write_managed(spec.path, canonical.name, content)
    result.written.append(spec.path)
    return result
