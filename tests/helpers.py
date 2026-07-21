"""Builders and lookups shared across unit tests."""

from __future__ import annotations

from pathlib import Path

from skillcraft.ir import ConfigDoc, Diagnostic, DocMeta
from skillcraft.plugins import registry


def rule_by_id(rule_id: str):
    """Fetch a registered rule instance by its SCxxx id."""
    return next(r for r in registry.all_rules() if r.id == rule_id)


def lint_doc(doc: ConfigDoc) -> list[Diagnostic]:
    """Run every applicable built-in rule against ``doc``; return diagnostics."""
    out: list[Diagnostic] = []
    for rule in registry.all_rules():
        if rule.formats and doc.meta.doc_type not in rule.formats:
            continue
        out.extend(rule.check(doc))
    return out


def skill_doc(
    name="good-skill",
    description="A useful skill that performs useful work in the repo.",
    body="# Body\n",
    path="good-skill/SKILL.md",
    extra=None,
    **kwargs,
) -> ConfigDoc:
    meta = DocMeta(
        source_path=Path(path),
        doc_type="skill",
        name=name,
        description=description,
        extra_frontmatter=extra or {},
    )
    return ConfigDoc(meta=meta, body=body, **kwargs)


def claude_doc(path, body="", imports=None) -> ConfigDoc:
    meta = DocMeta(source_path=Path(path), doc_type="claude")
    return ConfigDoc(meta=meta, body=body, imports=imports or [])


def agents_doc(path="AGENTS.md", body="") -> ConfigDoc:
    meta = DocMeta(source_path=Path(path), doc_type="agents")
    return ConfigDoc(meta=meta, body=body)
