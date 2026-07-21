"""Intermediate representation for agent-config documents.

Every format parser emits a :class:`ConfigDoc`; every renderer consumes one.
The IR is format-agnostic — it uses the *union* of all formats' fields, with an
``extra_frontmatter`` escape hatch so metadata we don't model is never silently
dropped. Same-format parse → render is lossless (converters keep verbatim
frontmatter text + body); cross-format sync is intentionally not lossless.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- document types ---------------------------------------------------------
TYPE_AGENTS = "agents"
TYPE_CLAUDE = "claude"
TYPE_CLAUDE_RULES = "claude_rules"
TYPE_SKILL = "skill"
TYPE_CURSOR = "cursor"
TYPE_COPILOT = "copilot"

# --- severities -------------------------------------------------------------
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"
_SEVERITY_RANK = {SEVERITY_ERROR: 3, SEVERITY_WARNING: 2, SEVERITY_INFO: 1}


def severity_rank(sev: str) -> int:
    """Higher = more severe. Unknown severities rank below INFO."""
    return _SEVERITY_RANK.get(sev, 0)


@dataclass(frozen=True)
class Diagnostic:
    """A single lint finding. Stable ``rule_id``; ``line``/``col`` are 1-indexed."""

    rule_id: str
    severity: str
    message: str
    file: str
    line: int | None = None
    col: int | None = None


@dataclass
class ImportRef:
    """An ``@path`` reference (CLAUDE.md / skill body)."""

    path: str
    resolved: Path | None  # absolute path if it exists on disk, else None
    line: int  # 1-indexed


@dataclass
class Section:
    """A markdown heading and the body text beneath it (until the next heading)."""

    heading: str  # verbatim heading line, e.g. "## Build"
    level: int  # number of leading '#'
    body: str
    start_line: int  # 1-indexed line of the heading


@dataclass
class DocMeta:
    """Identity + scoping metadata for a document. All optional except source/type."""

    source_path: Path
    doc_type: str
    name: str | None = None
    description: str | None = None
    scope_globs: list[str] = field(default_factory=list)
    scope_file_types: list[str] = field(default_factory=list)
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: list[str] | None = None
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigDoc:
    """The universal intermediate representation for an agent-config file."""

    meta: DocMeta
    body: str  # markdown body after frontmatter, verbatim
    frontmatter: dict[str, Any] | None = None  # parsed, for rules to read
    frontmatter_raw: str | None = None  # verbatim YAML block, for lossless render
    has_frontmatter: bool = False
    frontmatter_error: str | None = None  # set if YAML frontmatter failed to parse
    imports: list[ImportRef] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    line_offset: int = 0  # file lines preceding ``body`` (managed marker + frontmatter)

    @property
    def lines(self) -> list[str]:
        return self.body.splitlines()


# --- parsing helpers (text → IR fragments) ----------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_IMPORT_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_./\-]+)")


def split_frontmatter(text: str) -> tuple[str | None, str, int]:
    """Split leading ``---`` YAML frontmatter from the body.

    Returns ``(frontmatter_raw, body, lines_before_body)``. ``lines_before_body``
    is the number of lines consumed at the top (opening ``---``, the frontmatter
    content, and the closing ``---``) so callers can keep diagnostics
    file-relative. If there is no frontmatter (or it is malformed — no closing
    ``---``), returns ``(None, text, 0)``.
    """
    if not text.startswith("---"):
        return None, text, 0
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter_raw = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            return frontmatter_raw, body, i + 1  # lines[0..i] precede body
    return None, text, 0  # no closing delimiter → treat as plain body


def parse_sections(body: str, first_line: int = 1) -> list[Section]:
    sections: list[Section] = []
    cur: Section | None = None
    buf: list[str] = []
    for idx, line in enumerate(body.splitlines(), start=first_line):
        if _HEADING_RE.match(line):
            if cur is not None:
                cur.body = "\n".join(buf).strip("\n")
                sections.append(cur)
            cur = Section(
                heading=line.rstrip(),
                level=len(_HEADING_RE.match(line).group(1)),  # type: ignore[union-attr]
                body="",
                start_line=idx,
            )
            buf = []
        else:
            buf.append(line)
    if cur is not None:
        cur.body = "\n".join(buf).strip("\n")
        sections.append(cur)
    return sections


def find_imports(body: str, base_dir: Path, first_line: int = 1) -> list[ImportRef]:
    """Find ``@path`` references that look like file paths (contain ``/`` or ``.``)."""
    refs: list[ImportRef] = []
    for idx, line in enumerate(body.splitlines(), start=first_line):
        for m in _IMPORT_RE.finditer(line):
            token = m.group(1)
            if "/" not in token and "." not in token:
                continue  # bare @word (e.g. @anthropic) is not an import
            candidate = (base_dir / token).resolve()
            refs.append(
                ImportRef(path=token, resolved=candidate if candidate.exists() else None, line=idx)
            )
    return refs
