"""skillcraft HTML-comment conventions — the universal extension channel.

These comments are invisible to every real consumer (markdown renderers and
agent runtimes treat them as comments) but machine-readable to us. They let a
schema-less canonical ``AGENTS.md`` carry the richer metadata of SKILL.md /
.cursor rules without forking the standard.

Comment types:
* ``<!-- skillcraft:meta <json> -->``     — carried metadata (name, description, …)
* ``<!-- skillcraft:scope <json> -->``    — scope_globs a target can't express natively
* ``<!-- skillcraft:managed-source path=… -->`` — marks a sync-managed target
"""

from __future__ import annotations

import json
import re

META_RE = re.compile(r"<!--\s*skillcraft:meta\s+(.*?)\s*-->", re.DOTALL)
SCOPE_RE = re.compile(r"<!--\s*skillcraft:scope\s+(.*?)\s*-->", re.DOTALL)
MANAGED_RE = re.compile(r"<!--\s*skillcraft:managed-source\s+(.*?)\s*-->")

_MODELLED_META_KEYS = {
    "name",
    "description",
    "scope_globs",
    "scope_file_types",
    "allowed_tools",
    "license",
    "compatibility",
}


def parse_meta(body: str) -> dict:
    """Extract carried metadata from skillcraft:meta / skillcraft:scope comments."""
    out: dict = {}
    m = META_RE.search(body)
    if m:
        try:
            payload = json.loads(m.group(1))
            if isinstance(payload, dict):
                out.update(payload)
        except json.JSONDecodeError:
            pass
    s = SCOPE_RE.search(body)
    if s:
        try:
            scope = json.loads(s.group(1))
            if isinstance(scope, dict) and scope.get("globs"):
                out.setdefault("scope_globs", scope["globs"])
        except json.JSONDecodeError:
            pass
    return out


def extra_meta_keys(payload: dict) -> dict:
    """Return payload entries not in our modelled set (preserved verbatim)."""
    return {k: v for k, v in payload.items() if k not in _MODELLED_META_KEYS}


def strip_meta_comments(body: str) -> str:
    """Drop whole skillcraft:meta / skillcraft:scope comment lines; collapse blanks.

    Removing the entire line (not just the match text) avoids leaving orphan
    blank lines where a comment stood. Assumes single-line comments.
    """
    kept: list[str] = []
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if META_RE.fullmatch(stripped) or SCOPE_RE.fullmatch(stripped):
            continue
        kept.append(line)
    collapsed = "".join(kept)
    return re.sub(r"\n{3,}", "\n\n", collapsed)


def managed_marker(source_path: str) -> str:
    """The managed-source marker written at the top of a sync-managed target."""
    return f"<!-- skillcraft:managed-source path={source_path} -->"


def _parse_kv(s: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            pairs[k] = v
    return pairs


def parse_managed(text: str) -> dict[str, str] | None:
    m = MANAGED_RE.search(text)
    if not m:
        return None
    kv = _parse_kv(m.group(1))
    return kv or None


def strip_managed(text: str) -> tuple[str, int]:
    """Remove the managed-source marker line and any leading blank lines.

    Returns ``(stripped_text, lines_removed)`` where ``lines_removed`` is the
    number of file lines consumed at the top (the marker line plus any blank
    lines removed after it). Callers add this offset to body-relative line
    numbers so diagnostics point at the real on-disk line. ``0`` when there is
    no marker.

    The marker is sync infrastructure, not document content — every parser
    drops it. Removing the *whole* line (not just the match text) and stripping
    the blank line(s) it leaves at the top ensures a frontmatter block that must
    start at column 0 is still detected after a sync write prefixes the marker.
    Hand-authored files (no marker) are returned unchanged.

    The offset assumes the marker leads the file (the only placement ``sync``
    writes); a mid-file marker is still stripped but contributes a ``0`` offset.
    Legacy markers that also carried a ``sha=`` fingerprint still parse: only
    ``path`` is read, the rest is ignored.
    """
    m = MANAGED_RE.search(text)
    if m is None:
        return text, 0
    line_start = text.rfind("\n", 0, m.start()) + 1  # 0 when marker is on line 1
    nl = text.find("\n", m.end())
    line_end = len(text) if nl == -1 else nl + 1  # consume the marker's newline
    rest = text[:line_start] + text[line_end:]
    stripped = rest.lstrip("\n")
    if line_start == 0:
        leading_blanks = len(rest) - len(stripped)
        lines_removed = text.count("\n", 0, line_end + leading_blanks)
    else:
        lines_removed = 0  # mid-file marker: the file's top line numbers are unchanged
    return stripped, lines_removed
