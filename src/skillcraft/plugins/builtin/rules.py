"""Built-in lint rules (SCxxx).

Rule taxonomy (greppable IDs, never renumbered):
* SC1xx — SKILL.md
* SC2xx — CLAUDE.md
* SC3xx — universal (all formats)
* SC4xx — .cursor rules (v0.2)
"""

from __future__ import annotations

import re
from pathlib import Path

from skillcraft.ir import Diagnostic, find_imports
from skillcraft.plugins.api import Rule
from skillcraft.plugins.registry import register_rule
from skillcraft.tokens import estimate_tokens

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@register_rule
class SkillNameKebab(Rule):
    """SC101 — skill ``name`` is kebab-case, ≤64 chars, no leading/trailing/double hyphens."""

    id = "SC101"
    formats = ("skill",)
    severity = "error"

    def check(self, doc):
        name = doc.meta.name
        if not isinstance(name, str) or not name:
            return  # presence is SC301's job
        if len(name) > 64:
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill name '{name}' exceeds 64 characters",
                file=str(doc.meta.source_path),
            )
        if not _NAME_RE.match(name):
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill name '{name}' must be kebab-case (lowercase alphanumerics, single hyphens)",
                file=str(doc.meta.source_path),
            )


@register_rule
class SkillNameMatchesDir(Rule):
    """SC102 — in a ``skills/<name>/`` folder, skill ``name`` equals ``<name>``.

    Only enforced when the SKILL.md lives inside a directory whose parent is
    named ``skills`` (the conventional layout, e.g. ``.claude/skills/<name>/``).
    A repo-root ``SKILL.md`` has no enclosing skills folder and is skipped, so
    ``init``+``sync`` at a repo root never trips this rule.
    """

    id = "SC102"
    formats = ("skill",)
    severity = "error"

    def check(self, doc):
        name = doc.meta.name
        if not isinstance(name, str) or not name:
            return
        parent = doc.meta.source_path.resolve().parent
        if parent.parent.name.lower() != "skills":
            return  # not in a skills/<name>/ layout — convention does not apply
        if name != parent.name:
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill name '{name}' must match directory name '{parent.name}'",
                file=str(doc.meta.source_path),
            )


@register_rule
class SkillDescription(Rule):
    """SC103 — skill ``description`` ≤1024 chars (presence is SC301's job)."""

    id = "SC103"
    formats = ("skill",)
    severity = "error"

    def check(self, doc):
        desc = doc.meta.description
        if not isinstance(desc, str) or not desc.strip():
            return
        if len(desc) > 1024:
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill 'description' exceeds 1024 characters ({len(desc)})",
                file=str(doc.meta.source_path),
            )


@register_rule
class SkillDescriptionTooShort(Rule):
    """SC105 — skill ``description`` should be ≥40 chars for triggerability.

    Agents match skills on description text, so a terse description makes a
    skill hard to trigger. Presence (SC301) and the length ceiling (SC103) are
    owned elsewhere; this rule is purely about description *quality*.
    """

    id = "SC105"
    formats = ("skill",)
    severity = "warning"
    MIN_LENGTH = 40

    def check(self, doc):
        desc = doc.meta.description
        if not isinstance(desc, str) or not desc.strip():
            return  # missing/blank is SC301/SC103's job
        if len(desc) < self.MIN_LENGTH:
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill 'description' is {len(desc)} chars; "
                f"use >= {self.MIN_LENGTH} for triggerability",
                file=str(doc.meta.source_path),
            )


@register_rule
class SkillBodyTokens(Rule):
    """SC104 — skill body estimated <5000 tokens (warn past 4000)."""

    id = "SC104"
    formats = ("skill",)
    severity = "warning"

    def check(self, doc):
        tokens = estimate_tokens(doc.body)
        if tokens > 4000:
            yield Diagnostic(
                self.id,
                self.severity,
                f"skill body is ~{tokens} tokens (recommended <5000)",
                file=str(doc.meta.source_path),
            )


@register_rule
class ClaudeImports(Rule):
    """SC201 — CLAUDE.md @imports resolve, no cycles, ≤4 hops."""

    id = "SC201"
    formats = ("claude",)
    severity = "error"
    MAX_DEPTH = 4

    def check(self, doc):
        for imp in doc.imports:
            if imp.resolved is None:
                yield Diagnostic(
                    self.id,
                    "error",
                    f"unresolved @import '{imp.path}'",
                    file=str(doc.meta.source_path),
                    line=imp.line,
                )
        start = doc.meta.source_path.resolve()
        for imp in doc.imports:
            if imp.resolved is None:
                continue
            yield from self._walk(imp.resolved, depth=1, visited={start})

    def _walk(self, path: Path, depth: int, visited: set[Path]):
        resolved = path.resolve()
        if resolved in visited:
            yield Diagnostic(
                self.id,
                "warning",
                f"cyclic @import detected at '{path}'",
                file=str(path),
            )
            return
        if depth > self.MAX_DEPTH:
            yield Diagnostic(
                self.id,
                "warning",
                f"@import chain exceeds {self.MAX_DEPTH} hops at '{path}'",
                file=str(path),
            )
            return
        visited = visited | {resolved}
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return
        for imp in find_imports(text, path.parent):
            if imp.resolved is None:
                continue
            yield from self._walk(imp.resolved, depth + 1, visited)


@register_rule
class ClaudeLineCount(Rule):
    """SC202 — CLAUDE.md line count <200 (warn), <500 (error)."""

    id = "SC202"
    formats = ("claude",)
    severity = "warning"

    def check(self, doc):
        count = len(doc.body.splitlines())
        if count > 500:
            yield Diagnostic(
                self.id,
                "error",
                f"CLAUDE.md is {count} lines (exceeds 500)",
                file=str(doc.meta.source_path),
            )
        elif count > 200:
            yield Diagnostic(
                self.id,
                "warning",
                f"CLAUDE.md is {count} lines (exceeds 200; long files reduce adherence)",
                file=str(doc.meta.source_path),
            )


@register_rule
class RequiredFields(Rule):
    """SC301 — required frontmatter fields present iff the format requires them."""

    id = "SC301"
    formats = ()  # all formats
    severity = "error"

    def check(self, doc):
        if doc.meta.doc_type != "skill":
            return  # AGENTS.md / CLAUDE.md require no frontmatter
        if doc.frontmatter_error:
            yield Diagnostic(
                self.id,
                self.severity,
                f"SKILL.md has invalid YAML frontmatter: {doc.frontmatter_error}",
                file=str(doc.meta.source_path),
            )
            return
        if not doc.has_frontmatter:
            yield Diagnostic(
                self.id,
                self.severity,
                "SKILL.md is missing frontmatter (needs 'name' and 'description')",
                file=str(doc.meta.source_path),
            )
            return
        frontmatter = doc.frontmatter or {}
        if not frontmatter.get("name"):
            yield Diagnostic(
                self.id,
                self.severity,
                "SKILL.md frontmatter is missing required 'name'",
                file=str(doc.meta.source_path),
            )
        if not frontmatter.get("description"):
            yield Diagnostic(
                self.id,
                self.severity,
                "SKILL.md frontmatter is missing required 'description'",
                file=str(doc.meta.source_path),
            )


@register_rule
class NoMergeConflictMarkers(Rule):
    """SC302 — no merge-conflict markers lurking in the body."""

    id = "SC302"
    formats = ()  # all formats
    severity = "error"

    def check(self, doc):
        for idx, line in enumerate(doc.body.splitlines(), start=1):
            if line.startswith("<<<<<<<") or line.startswith(">>>>>>>"):
                yield Diagnostic(
                    self.id,
                    self.severity,
                    f"merge-conflict marker found: {line[:7]}",
                    file=str(doc.meta.source_path),
                    line=idx,
                )
            elif line.strip() == "=======":
                yield Diagnostic(
                    self.id,
                    self.severity,
                    "merge-conflict marker found: =======",
                    file=str(doc.meta.source_path),
                    line=idx,
                )


@register_rule
class MissingTrailingNewline(Rule):
    """SC304 — config files should end with a trailing newline.

    POSIX text files end with a newline; many tools and editors expect it.
    Universal rule (runs on every format). Only the body is checked, so an
    empty file or a frontmatter-only SKILL.md is left alone.
    """

    id = "SC304"
    formats = ()  # all formats
    severity = "warning"

    def check(self, doc):
        if doc.body and not doc.body.endswith("\n"):
            yield Diagnostic(
                self.id,
                self.severity,
                "file should end with a trailing newline",
                file=str(doc.meta.source_path),
            )
