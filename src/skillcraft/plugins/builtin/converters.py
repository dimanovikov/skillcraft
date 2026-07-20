"""Built-in format converters: AGENTS.md, SKILL.md, CLAUDE.md.

Each parses text → :class:`ConfigDoc` and renders ConfigDoc → text. Same-format
parse→render is lossless (verbatim frontmatter + body). Cross-format sync
strips ``skillcraft:meta`` comments because the target carries that data
natively (or doesn't need it) — see ARCHITECTURE.md §1.4.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from yaml import YAMLError

from skillcraft.ir import (
    TYPE_AGENTS,
    TYPE_CLAUDE,
    TYPE_CURSOR,
    TYPE_SKILL,
    ConfigDoc,
    DocMeta,
    find_imports,
    parse_sections,
    split_frontmatter,
)
from skillcraft.markers import extra_meta_keys, parse_meta, strip_managed, strip_meta_comments
from skillcraft.plugins.api import Converter
from skillcraft.plugins.registry import register_converter

# SKILL.md frontmatter keys skillcraft models; the rest is preserved verbatim.
_SKILL_FM_KEYS = {"name", "description", "license", "compatibility", "allowed-tools"}

# .cursor/rules/*.mdc frontmatter keys skillcraft models (description, globs,
# alwaysApply); anything else is preserved verbatim.
_CURSOR_FM_KEYS = {"description", "globs", "alwaysApply"}


def _split_globs(value: object) -> list[str]:
    """Cursor ``globs`` may be a single pattern string or a list of them."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _split_allowed_tools(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return value.split()
    return None


@register_converter
class AgentsConverter(Converter):
    """Canonical source format — schema-less markdown, metadata in comments."""

    format_id = TYPE_AGENTS

    def applies_to(self, path: Path) -> bool:
        return path.name.upper() == "AGENTS.MD"

    def parse(self, path: Path, text: str) -> ConfigDoc:
        payload = parse_meta(text)
        meta = DocMeta(
            source_path=Path(path),
            doc_type=TYPE_AGENTS,
            name=payload.get("name"),
            description=payload.get("description"),
            scope_globs=list(payload.get("scope_globs") or []),
            scope_file_types=list(payload.get("scope_file_types") or []),
            allowed_tools=payload.get("allowed_tools"),
            license=payload.get("license"),
            compatibility=payload.get("compatibility"),
            extra_frontmatter=extra_meta_keys(payload),
        )
        return ConfigDoc(
            meta=meta,
            body=text,
            has_frontmatter=False,
            sections=parse_sections(text),
        )

    def render(self, doc: ConfigDoc) -> str:
        # Canonical source: comments are legitimate content here, keep verbatim.
        return doc.body


@register_converter
class SkillConverter(Converter):
    """SKILL.md — YAML frontmatter (name, description, …) + markdown body."""

    format_id = TYPE_SKILL

    def applies_to(self, path: Path) -> bool:
        return path.name.upper() == "SKILL.MD"

    def parse(self, path: Path, text: str) -> ConfigDoc:
        text = strip_managed(text)  # drop sync marker so frontmatter is detected
        fm_raw, body = split_frontmatter(text)
        meta = DocMeta(source_path=Path(path), doc_type=TYPE_SKILL)
        frontmatter: dict | None = None
        frontmatter_error: str | None = None
        has_fm = fm_raw is not None

        if has_fm:
            try:
                parsed = yaml.safe_load(fm_raw)
            except YAMLError as exc:
                parsed = None
                frontmatter_error = str(exc)
            if parsed is None:
                frontmatter = {}
            elif isinstance(parsed, dict):
                frontmatter = parsed
                meta.name = parsed.get("name")
                meta.description = parsed.get("description")
                meta.license = parsed.get("license")
                meta.compatibility = parsed.get("compatibility")
                meta.allowed_tools = _split_allowed_tools(parsed.get("allowed-tools"))
                for key, val in parsed.items():
                    if key not in _SKILL_FM_KEYS:
                        meta.extra_frontmatter[key] = val
            else:
                frontmatter = {}
                frontmatter_error = "frontmatter is not a YAML mapping"

        base = Path(path).parent
        return ConfigDoc(
            meta=meta,
            body=body,
            frontmatter=frontmatter,
            frontmatter_raw=fm_raw,
            has_frontmatter=has_fm,
            frontmatter_error=frontmatter_error,
            sections=parse_sections(body),
            imports=find_imports(body, base),
        )

    def render(self, doc: ConfigDoc) -> str:
        body = strip_meta_comments(doc.body)
        fm_block = self._render_frontmatter(doc)
        if fm_block is None:
            return body
        if not fm_block.endswith("\n"):
            fm_block += "\n"
        return f"---\n{fm_block}---\n{body}"

    def _render_frontmatter(self, doc: ConfigDoc) -> str | None:
        # Lossless same-format: reproduce verbatim. Sync/built: emit from meta.
        if doc.frontmatter_raw is not None:
            return doc.frontmatter_raw
        ordered: dict[str, object] = {}
        if doc.meta.name is not None:
            ordered["name"] = doc.meta.name
        if doc.meta.description is not None:
            ordered["description"] = doc.meta.description
        if doc.meta.license is not None:
            ordered["license"] = doc.meta.license
        if doc.meta.compatibility is not None:
            ordered["compatibility"] = doc.meta.compatibility
        if doc.meta.allowed_tools is not None:
            ordered["allowed-tools"] = " ".join(doc.meta.allowed_tools)
        for key in sorted(doc.meta.extra_frontmatter):
            ordered[key] = doc.meta.extra_frontmatter[key]
        if not ordered:
            return None
        return yaml.safe_dump(
            ordered, sort_keys=False, default_flow_style=False, allow_unicode=True
        )


@register_converter
class ClaudeConverter(Converter):
    """CLAUDE.md — plain markdown, no frontmatter, supports @path imports."""

    format_id = TYPE_CLAUDE

    def applies_to(self, path: Path) -> bool:
        return path.name.upper() == "CLAUDE.MD"

    def parse(self, path: Path, text: str) -> ConfigDoc:
        text = strip_managed(text)  # drop sync marker; body/line-counts stay accurate
        base = Path(path).parent
        meta = DocMeta(source_path=Path(path), doc_type=TYPE_CLAUDE)
        return ConfigDoc(
            meta=meta,
            body=text,
            has_frontmatter=False,
            sections=parse_sections(text),
            imports=find_imports(text, base),
        )

    def render(self, doc: ConfigDoc) -> str:
        return strip_meta_comments(doc.body)


@register_converter
class CursorConverter(Converter):
    """Cursor ``.cursor/rules/*.mdc`` — YAML frontmatter + markdown body.

    Frontmatter fields: ``description`` (→ ``meta.description``), ``globs``
    (→ ``meta.scope_globs``; the only format that scopes natively on globs),
    ``alwaysApply`` (capability flag, preserved). Everything else is kept
    verbatim via ``extra_frontmatter``. Same-format parse→render is lossless
    (verbatim frontmatter replayed); cross-format sync from ``AGENTS.md``
    builds frontmatter from meta, mapping ``scope_globs`` back to ``globs``.
    """

    format_id = TYPE_CURSOR

    def applies_to(self, path: Path) -> bool:
        if path.suffix != ".mdc":
            return False
        parts = path.parts
        return any(parts[i] == ".cursor" and parts[i + 1] == "rules" for i in range(len(parts) - 1))

    def parse(self, path: Path, text: str) -> ConfigDoc:
        text = strip_managed(text)  # drop sync marker so frontmatter is detected
        fm_raw, body = split_frontmatter(text)
        meta = DocMeta(source_path=Path(path), doc_type=TYPE_CURSOR)
        frontmatter: dict | None = None
        frontmatter_error: str | None = None
        has_fm = fm_raw is not None

        if has_fm:
            try:
                parsed = yaml.safe_load(fm_raw)
            except YAMLError as exc:
                parsed = None
                frontmatter_error = str(exc)
            if parsed is None:
                frontmatter = {}
            elif isinstance(parsed, dict):
                frontmatter = parsed
                meta.description = parsed.get("description")
                meta.scope_globs = _split_globs(parsed.get("globs"))
                for key, val in parsed.items():
                    if key not in _CURSOR_FM_KEYS:
                        meta.extra_frontmatter[key] = val
            else:
                frontmatter = {}
                frontmatter_error = "frontmatter is not a YAML mapping"

        return ConfigDoc(
            meta=meta,
            body=body,
            frontmatter=frontmatter,
            frontmatter_raw=fm_raw,
            has_frontmatter=has_fm,
            frontmatter_error=frontmatter_error,
            sections=parse_sections(body),
        )

    def render(self, doc: ConfigDoc) -> str:
        body = strip_meta_comments(doc.body)
        fm_block = self._render_frontmatter(doc)
        if fm_block is None:
            return body
        if not fm_block.endswith("\n"):
            fm_block += "\n"
        return f"---\n{fm_block}---\n{body}"

    def _render_frontmatter(self, doc: ConfigDoc) -> str | None:
        # Lossless same-format: reproduce verbatim. Sync/built: emit from meta.
        if doc.frontmatter_raw is not None:
            return doc.frontmatter_raw
        ordered: dict[str, object] = {}
        if doc.meta.description is not None:
            ordered["description"] = doc.meta.description
        if doc.meta.scope_globs:
            # Cursor accepts a single string or a list; emit the minimal form.
            globs = doc.meta.scope_globs
            ordered["globs"] = globs[0] if len(globs) == 1 else globs
        always = doc.meta.extra_frontmatter.get("alwaysApply")
        if always is not None:
            ordered["alwaysApply"] = always
        for key in sorted(doc.meta.extra_frontmatter):
            if key == "alwaysApply":
                continue
            ordered[key] = doc.meta.extra_frontmatter[key]
        if not ordered:
            return None
        return yaml.safe_dump(
            ordered, sort_keys=False, default_flow_style=False, allow_unicode=True
        )
