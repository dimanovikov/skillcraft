"""Unit tests for the agents/skill/claude converters: round-trips, cross-format, determinism."""

from __future__ import annotations

from pathlib import Path

from skillcraft.plugins.registry import get_converter
from skillcraft.sync import render_target

AGENTS = (
    '<!-- skillcraft:meta {"name":"demo-skill","description":"A demo skill."} -->\n\n'
    "# demo-skill\n\nBody text.\n"
)
HAND_SKILL = (
    "---\nname: demo-skill\ndescription: A demo.\nversion: '1.0'\n---\n\n# demo-skill\n\nBody.\n"
)


def _conv(fmt_id):
    return get_converter(fmt_id)


class TestAgentsConverter:
    def test_parse_extracts_meta(self):
        doc = _conv("agents").parse(Path("AGENTS.md"), AGENTS)
        assert doc.meta.name == "demo-skill"
        assert doc.meta.description == "A demo skill."
        assert doc.meta.doc_type == "agents"

    def test_render_is_verbatim_lossless(self):
        c = _conv("agents")
        doc = c.parse(Path("AGENTS.md"), AGENTS)
        assert c.render(doc) == AGENTS

    def test_applies_to(self):
        assert _conv("agents").applies_to(Path("AGENTS.md"))
        assert _conv("agents").applies_to(Path("sub/agents.md"))
        assert not _conv("agents").applies_to(Path("SKILL.md"))


class TestSkillConverter:
    def test_parse_frontmatter_and_extra(self):
        doc = _conv("skill").parse(Path("demo-skill/SKILL.md"), HAND_SKILL)
        assert doc.meta.name == "demo-skill"
        assert doc.meta.description == "A demo."
        assert doc.has_frontmatter
        assert doc.frontmatter["version"] == "1.0"
        assert doc.meta.extra_frontmatter == {"version": "1.0"}

    def test_same_format_lossless(self):
        c = _conv("skill")
        doc = c.parse(Path("demo-skill/SKILL.md"), HAND_SKILL)
        assert c.render(doc) == HAND_SKILL

    def test_managed_marker_does_not_hide_frontmatter(self):
        # regression: a sync-managed SKILL.md prefixes a marker before the `---`
        managed = "<!-- skillcraft:managed-source path=AGENTS.md sha=abc -->\n\n" + HAND_SKILL
        doc = _conv("skill").parse(Path("demo-skill/SKILL.md"), managed)
        assert doc.has_frontmatter
        assert doc.meta.name == "demo-skill"

    def test_render_from_agents_builds_frontmatter(self):
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), AGENTS)
        out = _conv("skill").render(agents_doc)
        assert out.startswith("---\n")
        assert "name: demo-skill" in out
        assert "description: A demo skill." in out
        assert "managed-source" not in out
        assert "<!-- skillcraft:meta" not in out  # meta comment stripped for skill target

    def test_invalid_yaml_sets_error(self):
        bad = "---\nname: [unclosed\n---\nbody\n"
        doc = _conv("skill").parse(Path("SKILL.md"), bad)
        assert doc.frontmatter_error is not None


class TestClaudeConverter:
    def test_parse_finds_imports(self, tmp_path):
        (tmp_path / "dep.md").write_text("x", encoding="utf-8")
        doc = _conv("claude").parse(tmp_path / "CLAUDE.md", "see @dep.md\n")
        assert len(doc.imports) == 1
        assert doc.imports[0].resolved is not None

    def test_render_strips_meta_comments(self):
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), AGENTS)
        out = _conv("claude").render(agents_doc)
        assert "<!-- skillcraft:meta" not in out
        assert "# demo-skill" in out

    def test_same_format_lossless(self):
        c = _conv("claude")
        text = "# Title\n\nplain body, no skillcraft comments\n"
        doc = c.parse(Path("CLAUDE.md"), text)
        assert c.render(doc) == text


class TestCrossFormatAndDeterminism:
    def test_render_target_skill_and_claude(self):
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), AGENTS)
        skill = render_target(agents_doc, "skill")
        claude = render_target(agents_doc, "claude")
        assert skill is not None and skill.startswith("---\n")
        assert claude is not None and "# demo-skill" in claude

    def test_render_target_skill_none_without_meta(self):
        # an AGENTS.md with no name/description meta cannot build a SKILL.md
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), "# just docs\n")
        assert render_target(agents_doc, "skill") is None

    def test_render_is_deterministic(self):
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), AGENTS)
        assert render_target(agents_doc, "skill") == render_target(agents_doc, "skill")
        assert render_target(agents_doc, "claude") == render_target(agents_doc, "claude")


RICH_SKILL = (
    "---\n"
    "name: demo-skill\n"
    "description: A demo.\n"
    "license: MIT\n"
    "compatibility: '>=1.0'\n"
    "allowed-tools:\n"
    "  - Bash\n"
    "  - Read\n"
    "version: '1.0'\n"
    "---\n\n# demo-skill\n\nBody.\n"
)


class TestRichFrontmatter:
    def test_parse_splits_allowed_tools_and_extras(self):
        doc = _conv("skill").parse(Path("demo-skill/SKILL.md"), RICH_SKILL)
        assert doc.meta.license == "MIT"
        assert doc.meta.compatibility == ">=1.0"
        assert doc.meta.allowed_tools == ["Bash", "Read"]
        assert doc.meta.extra_frontmatter == {"version": "1.0"}

    def test_same_format_lossless(self):
        c = _conv("skill")
        doc = c.parse(Path("demo-skill/SKILL.md"), RICH_SKILL)
        assert c.render(doc) == RICH_SKILL

    def test_render_from_agents_includes_all_meta_fields(self):
        rich_agents = (
            '<!-- skillcraft:meta {"name":"demo","description":"d","license":"MIT",'
            '"compatibility":">=1.0","allowed_tools":["Bash","Read"]} -->\n\n# demo\n\nBody.\n'
        )
        agents_doc = _conv("agents").parse(Path("AGENTS.md"), rich_agents)
        out = _conv("skill").render(agents_doc)
        assert "license: MIT" in out
        assert ">=1.0" in out
        assert "allowed-tools: Bash Read" in out


def test_frontmatter_not_a_mapping_sets_error():
    doc = _conv("skill").parse(Path("SKILL.md"), "---\njustastring\n---\nbody\n")
    assert doc.frontmatter_error is not None
    assert "not a YAML mapping" in doc.frontmatter_error


CURSOR_MDC = (
    "---\n"
    "description: Python guardrails\n"
    "globs: '**/*.py'\n"
    "alwaysApply: false\n"
    "---\n\n"
    "# Python rules\n\nUse type hints.\n"
)


class TestCursorConverter:
    def test_applies_to(self):
        c = _conv("cursor")
        assert c.applies_to(Path(".cursor/rules/python.mdc"))
        assert c.applies_to(Path("repo/.cursor/rules/sub/x.mdc"))
        assert not c.applies_to(Path(".cursor/rules/python.md"))  # wrong suffix
        assert not c.applies_to(Path("rules/x.mdc"))  # not under .cursor
        assert not c.applies_to(Path(".cursor/x.mdc"))  # not under rules

    def test_parse_maps_globs_to_scope(self):
        doc = _conv("cursor").parse(Path(".cursor/rules/python.mdc"), CURSOR_MDC)
        assert doc.meta.doc_type == "cursor"
        assert doc.meta.description == "Python guardrails"
        assert doc.meta.scope_globs == ["**/*.py"]
        assert doc.has_frontmatter

    def test_parse_globs_list(self):
        mdc = "---\nglobs:\n  - '*.py'\n  - '*.pyi'\n---\n\nbody\n"
        doc = _conv("cursor").parse(Path(".cursor/rules/x.mdc"), mdc)
        assert doc.meta.scope_globs == ["*.py", "*.pyi"]

    def test_parse_preserves_unknown_keys(self):
        mdc = "---\ndescription: d\ncustomField: yes\n---\n\nbody\n"
        doc = _conv("cursor").parse(Path(".cursor/rules/x.mdc"), mdc)
        assert doc.meta.extra_frontmatter == {"customField": True}

    def test_same_format_lossless(self):
        c = _conv("cursor")
        doc = c.parse(Path(".cursor/rules/python.mdc"), CURSOR_MDC)
        assert c.render(doc) == CURSOR_MDC

    def test_render_from_agents_emits_globs(self):
        agents = (
            '<!-- skillcraft:meta {"name":"d","description":"Python guardrails.",'
            '"scope_globs":["**/*.py"]} -->\n\n# d\n\nbody.\n'
        )
        adoc = _conv("agents").parse(Path("AGENTS.md"), agents)
        out = _conv("cursor").render(adoc)
        assert out.startswith("---\n")
        assert "description: Python guardrails." in out
        assert "**/*.py" in out
        assert "<!-- skillcraft:meta" not in out
