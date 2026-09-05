"""Report formatters: plain, json, github (PR annotations), sarif (code scanning)."""

from __future__ import annotations

import json
from pathlib import PurePath, PureWindowsPath

from skillcraft import __version__
from skillcraft.ir import Diagnostic

_GH_SEVERITY = {"error": "error", "warning": "warning", "info": "notice"}

# SARIF 2.1.0 ``level`` is one of none | note | warning | error.
_SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}


def _sorted(diags: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(diags, key=lambda d: (d.file, d.line or 0, d.rule_id))


def _posix_uri(path: str) -> str:
    """Normalize a path to a POSIX URI on every host.

    ``PurePath`` is ``PurePosixPath`` on macOS/Linux and treats a backslash as
    a regular character, so a Windows-style path is left intact and yields an
    invalid artifact/annotation URI. A path containing a backslash is treated
    as Windows-style and converted here.
    """
    if "\\" in path:
        return PureWindowsPath(path).as_posix()
    return PurePath(path).as_posix()


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
        file = _posix_uri(d.file)
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


def format_sarif(diags: list[Diagnostic]) -> str:
    """SARIF 2.1.0 report — upload to GitHub → Security → Code scanning.

    One ``result`` per diagnostic (``ruleId`` = ``SCxxx``); ``level`` maps from
    severity (``error``→``error``, ``warning``→``warning``, ``info``→``note``).
    Paths are normalized to POSIX so ``artifactLocation.uri`` resolves cleanly
    on every platform. The driver's ``rules`` list is derived from the rule ids
    actually present so GitHub can render rule metadata.
    """
    results: list[dict] = []
    rule_ids: set[str] = set()
    for d in _sorted(diags):
        rule_ids.add(d.rule_id)
        physical: dict = {"artifactLocation": {"uri": _posix_uri(d.file)}}
        region: dict = {}
        if d.line:
            region["startLine"] = d.line
        if d.col:
            region["startColumn"] = d.col
        if region:
            physical["region"] = region
        results.append(
            {
                "ruleId": d.rule_id,
                "level": _SARIF_LEVEL.get(d.severity, "warning"),
                "message": {"text": d.message},
                "locations": [{"physicalLocation": physical}],
            }
        )

    report = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skillcraft",
                        "version": __version__,
                        "informationUri": "https://github.com/dimanovikov/skillcraft",
                        "rules": [{"id": rid} for rid in sorted(rule_ids)],
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
