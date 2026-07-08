"""Report formatters: plain, json, github (PR annotations)."""

from __future__ import annotations

import json
from pathlib import PurePath

from skillcraft.ir import Diagnostic

_GH_SEVERITY = {"error": "error", "warning": "warning", "info": "notice"}


def _sorted(diags: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(diags, key=lambda d: (d.file, d.line or 0, d.rule_id))


def format_plain(diags: list[Diagnostic]) -> str:
    if not diags:
        return "No issues found."
    lines = []
    for d in _sorted(diags):
        loc = f"{d.file}:{d.line}" if d.line else d.file
        lines.append(f"{loc}: {d.severity}: {d.rule_id} {d.message}")
    return "\n".join(lines)


def format_json(diags: list[Diagnostic]) -> str:
    return json.dumps(
        [
            {
                "rule_id": d.rule_id,
                "severity": d.severity,
                "message": d.message,
                "file": d.file,
                "line": d.line,
                "col": d.col,
            }
            for d in _sorted(diags)
        ],
        indent=2,
        ensure_ascii=False,
    )


def format_github(diags: list[Diagnostic]) -> str:
    """GitHub Actions annotation format — shows inline on PR diffs.

    Paths are normalized to POSIX separators so the ``file=`` attribute resolves
    to a clickable, repo-relative link on every platform.
    """
    out = []
    for d in _sorted(diags):
        sev = _GH_SEVERITY.get(d.severity, "notice")
        file = PurePath(d.file).as_posix()
        cmd = f"::{sev} file={file}"
        if d.line:
            cmd += f",line={d.line}"
        if d.col:
            cmd += f",col={d.col}"
        cmd += f"::{d.rule_id} {d.message}"
        out.append(cmd)
    return "\n".join(out)


def has_errors(diags: list[Diagnostic]) -> bool:
    return any(d.severity == "error" for d in diags)
