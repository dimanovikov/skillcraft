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
class CursorGlobsValid(Rule):
    """SC401 — Cursor rule globs are well-formed and the rule is reachable.

    A ``.mdc`` rule applies either when its ``globs`` match the open file or
    when ``alwaysApply: true``. With neither, the rule silently never fires.
    Errors on a malformed ``globs`` type; warns on a rule that has no globs
    and ``alwaysApply`` not set to true.
    """

    id = "SC401"
    formats = ("cursor",)
    severity = "error"

    def check(self, doc):
        fm = doc.frontmatter or {}
        globs = fm.get("globs")
        if globs is not None and not isinstance(globs, (str, list)):
            yield Diagnostic(
                self.id,
                "error",
                "'globs' must be a string or list of glob patterns",
                file=str(doc.meta.source_path),
            )
            return
        always = bool(fm.get("alwaysApply", False))
        globs_empty = (
            globs is None
            or (isinstance(globs, str) and not globs.strip())
            or (isinstance(globs, list) and len(globs) == 0)
        )
        if not always and globs_empty:
            yield Diagnostic(
                self.id,
                "warning",
                "Cursor rule has no globs and alwaysApply is false — it will never trigger",
                file=str(doc.meta.source_path),
            )


@register_rule
class CursorAlwaysApplyConflict(Rule):
    """SC402 — warn when ``alwaysApply: true`` and ``globs`` are both set.

    Cursor ignores ``globs`` when ``alwaysApply`` is true, so specifying both
    is misleading. Warn so the author picks one or the other.
    """

    id = "SC402"
    formats = ("cursor",)
    severity = "warning"

    def check(self, doc):
        fm = doc.frontmatter or {}
        if not bool(fm.get("alwaysApply", False)):
            return
        globs = fm.get("globs")
        has_globs = (isinstance(globs, str) and globs.strip()) or (
            isinstance(globs, list) and len(globs) > 0
        )
        if has_globs:
            yield Diagnostic(
                self.id,
                self.severity,
                "'alwaysApply: true' ignores globs — set one or the other",
                file=str(doc.meta.source_path),
            )
