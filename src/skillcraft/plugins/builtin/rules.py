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


def _repo_root(path: Path) -> Path | None:
    """Walk up from ``path`` to the nearest ancestor containing a ``.git`` dir/file.

    Returns ``None`` when no repository boundary can be found (e.g. an ad-hoc
    file outside any repo), so callers can choose to skip enforcement.
    """
    p = path.resolve()
    if p.is_file():
        p = p.parent
    for parent in (p, *p.parents):
        if (parent / ".git").exists():
            return parent
    return None


@register_rule
class ClaudeImportScope(Rule):
    """SC203 — CLAUDE.md @imports must resolve inside the repository.

    An import that resolves *above* the repo root (``@../../secrets.md``-style)
    is almost always a mistake or an accidental leak. Errors on any resolved
    import whose path escapes the repo root. Unresolved imports are SC201's job.
    """

    id = "SC203"
    formats = ("claude",)
    severity = "error"

    def check(self, doc):
        root = _repo_root(doc.meta.source_path)
        if root is None:
            return  # no repo boundary to enforce
        for imp in doc.imports:
            if imp.resolved is None:
                continue  # unresolved is SC201's job
            try:
                imp.resolved.relative_to(root)
            except ValueError:
                yield Diagnostic(
                    self.id,
                    self.severity,
                    f"@import '{imp.path}' resolves outside the repo root",
                    file=str(doc.meta.source_path),
                    line=imp.line,
                )


@register_rule
class SkippedHeadingLevels(Rule):
    """SC204 — warn when a heading jumps more than one level (``#`` → ``###``).

    Skipping levels hurts readability and breaks TOC generators. Going back up
    (``###`` → ``#``) is fine; only an *increase* greater than 1 is flagged.
    Universal rule — runs on every format whose body is parsed into sections.
    """

    id = "SC204"
    formats = ()  # all formats
    severity = "warning"

    def check(self, doc):
        prev = None
        for section in doc.sections:
            if prev is not None and section.level - prev > 1:
                heading = section.heading.strip()
                yield Diagnostic(
                    self.id,
                    self.severity,
                    f"heading '{heading}' jumps from level {prev} to {section.level}",
                    file=str(doc.meta.source_path),
                    line=section.start_line,
                )
            prev = section.level


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
        for idx, line in enumerate(doc.body.splitlines(), start=doc.line_offset + 1):
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


def _cursor_always_apply(fm: dict) -> tuple[bool, bool]:
    """Read Cursor ``alwaysApply`` strictly.

    Returns ``(is_true, valid)``. Non-boolean values (quoted strings, numbers)
    are ``valid=False`` so callers emit a type error instead of misreading a
    truthy string like ``"false"`` as enabled. (``bool`` is checked before any
    numeric handling because ``bool`` subclasses ``int``.)
    """
    raw = fm.get("alwaysApply")
    if raw is None:
        return False, True
    if isinstance(raw, bool):
        return raw, True
    return False, False


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
        always, valid = _cursor_always_apply(fm)
        if not valid:
            yield Diagnostic(
                self.id,
                "error",
                "'alwaysApply' must be a boolean (true/false), not a string or number",
                file=str(doc.meta.source_path),
            )
            return
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
        always, valid = _cursor_always_apply(fm)
        if not valid or not always:
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
