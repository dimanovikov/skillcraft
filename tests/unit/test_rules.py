"""Parametrized unit tests for the built-in lint rules (SC101–SC302)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillcraft.ir import ConfigDoc, DocMeta, ImportRef, find_imports, parse_sections
from tests.helpers import agents_doc, claude_doc, lint_doc, rule_by_id, skill_doc


class TestSC101NameKebab:
    @pytest.mark.parametrize("name", ["good-skill", "a", "ab", "a-b-c", "skill2", "2-thing"])
    def test_valid(self, name):
        assert list(rule_by_id("SC101").check(skill_doc(name=name))) == []

    @pytest.mark.parametrize("name", ["Bad_Name", "Bad", "-bad", "bad-", "bad--name", "UPPER"])
    def test_invalid(self, name):
        diags = list(rule_by_id("SC101").check(skill_doc(name=name)))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC101"

    def test_too_long(self):
        diags = list(rule_by_id("SC101").check(skill_doc(name="a" * 65)))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC101"

    def test_missing_name_skipped(self):
        # presence is SC301's job; SC101 yields nothing when name is absent
        assert list(rule_by_id("SC101").check(skill_doc(name=None))) == []


class TestSC102NameMatchesDir:
    def test_matches(self, tmp_path):
        p = tmp_path / "skills" / "my-skill" / "SKILL.md"
        p.parent.mkdir(parents=True)
        assert list(rule_by_id("SC102").check(skill_doc(name="my-skill", path=str(p)))) == []

    def test_mismatch(self, tmp_path):
        p = tmp_path / "skills" / "other-name" / "SKILL.md"
        p.parent.mkdir(parents=True)
        doc = skill_doc(name="my-skill", path=str(p))
        diags = list(rule_by_id("SC102").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC102"

    def test_skipped_at_repo_root(self, tmp_path):
        # a SKILL.md at the repo root has no enclosing skills/ folder → N/A
        p = tmp_path / "SKILL.md"
        assert list(rule_by_id("SC102").check(skill_doc(name="anything", path=str(p)))) == []


class TestSC103Description:
    def test_valid(self):
        assert (
            list(
                rule_by_id("SC103").check(skill_doc(description="A reasonable length description."))
            )
            == []
        )

    def test_too_long(self):
        diags = list(rule_by_id("SC103").check(skill_doc(description="x" * 1025)))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC103"

    def test_blank_skipped(self):
        assert list(rule_by_id("SC103").check(skill_doc(description="   "))) == []

    def test_none_skipped(self):
        assert list(rule_by_id("SC103").check(skill_doc(description=None))) == []


class TestSC105DescriptionTooShort:
    def test_too_short_warns(self):
        diags = list(rule_by_id("SC105").check(skill_doc(description="Fix it.")))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC105"
        assert diags[0].severity == "warning"
        assert "40" in diags[0].message

    def test_valid_length_ok(self):
        assert (
            list(
                rule_by_id("SC105").check(
                    skill_doc(description="Lint, sync and scaffold agent-config files.")
                )
            )
            == []
        )

    @pytest.mark.parametrize("length", [40, 41])
    def test_at_or_above_threshold_ok(self, length):
        assert list(rule_by_id("SC105").check(skill_doc(description="a" * length))) == []

    @pytest.mark.parametrize("length", [1, 39])
    def test_below_threshold_warns(self, length):
        diags = list(rule_by_id("SC105").check(skill_doc(description="a" * length)))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC105"

    def test_none_skipped(self):
        assert list(rule_by_id("SC105").check(skill_doc(description=None))) == []

    def test_blank_skipped(self):
        assert list(rule_by_id("SC105").check(skill_doc(description="   "))) == []


class TestSC104BodyTokens:
    def test_small_body_ok(self):
        assert list(rule_by_id("SC104").check(skill_doc(body="# short\n"))) == []

    def test_large_body_warns(self):
        body = "word " * 4000  # ~20000 chars → ~5000 tokens
        diags = list(rule_by_id("SC104").check(skill_doc(body=body)))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC104"
        assert diags[0].severity == "warning"


class TestSC201Imports:
    def test_unresolved_is_error(self, tmp_path):
        doc = claude_doc(
            tmp_path / "CLAUDE.md",
            body="see @missing.md\n",
            imports=[ImportRef(path="missing.md", resolved=None, line=1)],
        )
        diags = list(rule_by_id("SC201").check(doc))
        assert any(d.rule_id == "SC201" and d.severity == "error" for d in diags)

    def test_resolved_clean(self, tmp_path):
        (tmp_path / "dep.md").write_text("no further imports\n", encoding="utf-8")
        doc = claude_doc(
            tmp_path / "CLAUDE.md",
            body="see @dep.md\n",
            imports=find_imports("see @dep.md\n", tmp_path),
        )
        assert list(rule_by_id("SC201").check(doc)) == []

    def test_cycle_warns(self, tmp_path):
        a = tmp_path / "A.md"
        b = tmp_path / "B.md"
        a.write_text("see @B.md\n", encoding="utf-8")
        b.write_text("back @A.md\n", encoding="utf-8")
        text = a.read_text(encoding="utf-8")
        doc = claude_doc(a, body=text, imports=find_imports(text, tmp_path))
        diags = list(rule_by_id("SC201").check(doc))
        assert any(d.rule_id == "SC201" and "cyclic" in d.message for d in diags)

    def test_deep_chain_warns(self, tmp_path):
        # a → b → c → d → e → f : 5 hops to f exceeds MAX_DEPTH (4)
        names = ["a", "b", "c", "d", "e", "f"]
        files = {n: tmp_path / f"{n}.md" for n in names}
        for n, nxt in zip(names, names[1:], strict=False):
            files[n].write_text(f"see @{nxt}.md\n", encoding="utf-8")
        files["f"].write_text("end\n", encoding="utf-8")
        text = files["a"].read_text(encoding="utf-8")
        doc = claude_doc(files["a"], body=text, imports=find_imports(text, tmp_path))
        diags = list(rule_by_id("SC201").check(doc))
        assert any(d.rule_id == "SC201" and "exceeds" in d.message for d in diags)


class TestSC202LineCount:
    def test_short_ok(self):
        assert list(rule_by_id("SC202").check(claude_doc("CLAUDE.md", body="short\n"))) == []

    def test_warn_over_200(self):
        body = "\n".join(f"l{i}" for i in range(201)) + "\n"
        diags = list(rule_by_id("SC202").check(claude_doc("CLAUDE.md", body=body)))
        assert len(diags) == 1
        assert diags[0].severity == "warning"

    def test_error_over_500(self):
        body = "\n".join(f"l{i}" for i in range(501)) + "\n"
        diags = list(rule_by_id("SC202").check(claude_doc("CLAUDE.md", body=body)))
        assert len(diags) == 1
        assert diags[0].severity == "error"


class TestSC203ImportScope:
    def _repo(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        (root / ".git").mkdir()  # mark a repo boundary
        return root

    def test_import_outside_root_errors(self, tmp_path):
        root = self._repo(tmp_path)
        (tmp_path / "secrets.md").write_text("leaked\n", encoding="utf-8")
        body = "see @../secrets.md\n"
        doc = claude_doc(root / "CLAUDE.md", body=body, imports=find_imports(body, root))
        diags = list(rule_by_id("SC203").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC203"
        assert diags[0].severity == "error"

    def test_import_inside_root_ok(self, tmp_path):
        root = self._repo(tmp_path)
        (root / "docs").mkdir()
        (root / "docs" / "policy.md").write_text("ok\n", encoding="utf-8")
        body = "see @docs/policy.md\n"
        doc = claude_doc(root / "CLAUDE.md", body=body, imports=find_imports(body, root))
        assert list(rule_by_id("SC203").check(doc)) == []

    def test_no_repo_skipped(self, tmp_path):
        # no .git boundary → cannot determine scope, skip silently
        doc = claude_doc(
            tmp_path / "CLAUDE.md",
            body="see @x.md\n",
            imports=[ImportRef("x.md", None, 1)],
        )
        assert list(rule_by_id("SC203").check(doc)) == []

    def test_unresolved_skipped(self, tmp_path):
        # unresolved imports are SC201's job, not SC203's
        root = self._repo(tmp_path)
        doc = claude_doc(
            root / "CLAUDE.md",
            body="see @missing.md\n",
            imports=[ImportRef("missing.md", None, 1)],
        )
        assert list(rule_by_id("SC203").check(doc)) == []


class TestSC204SkippedHeadings:
    def _doc(self, body, doc_type="claude"):
        return ConfigDoc(
            meta=DocMeta(source_path=Path("CLAUDE.md"), doc_type=doc_type),
            body=body,
            sections=parse_sections(body),
        )

    def test_skip_1_to_3_warns(self):
        diags = list(rule_by_id("SC204").check(self._doc("# Title\n\n### Sub\n")))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC204"
        assert diags[0].severity == "warning"
        assert diags[0].line == 3  # the '### Sub' line

    def test_sequential_levels_ok(self):
        assert list(rule_by_id("SC204").check(self._doc("# A\n\n## B\n\n### C\n"))) == []

    def test_going_up_ok(self):
        # decreasing levels (### → #) is fine, not a skip
        assert list(rule_by_id("SC204").check(self._doc("### A\n\n# B\n"))) == []

    def test_first_heading_any_level_ok(self):
        # starting at h3 with no prior heading is not a skip
        assert list(rule_by_id("SC204").check(self._doc("### First\n"))) == []

    def test_no_headings_ok(self):
        assert list(rule_by_id("SC204").check(self._doc("plain text only\n"))) == []

    def test_runs_on_skill(self):
        # universal — also flags jumps in SKILL bodies
        diags = list(rule_by_id("SC204").check(self._doc("# T\n\n### S\n", "skill")))
        assert len(diags) == 1


class TestSC301RequiredFields:
    def test_valid_skill(self):
        doc = skill_doc(
            frontmatter={"name": "good-skill", "description": "y"}, has_frontmatter=True
        )
        assert list(rule_by_id("SC301").check(doc)) == []

    def test_missing_frontmatter(self):
        doc = skill_doc(has_frontmatter=False, frontmatter=None)
        diags = list(rule_by_id("SC301").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC301"

    def test_frontmatter_error(self):
        doc = skill_doc(has_frontmatter=True, frontmatter=None, frontmatter_error="bad yaml")
        diags = list(rule_by_id("SC301").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC301"

    def test_missing_name(self):
        doc = skill_doc(frontmatter={"description": "y"}, has_frontmatter=True)
        diags = list(rule_by_id("SC301").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC301"

    def test_missing_description(self):
        doc = skill_doc(frontmatter={"name": "x"}, has_frontmatter=True)
        diags = list(rule_by_id("SC301").check(doc))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC301"

    def test_non_skill_skipped(self):
        assert list(rule_by_id("SC301").check(agents_doc())) == []


class TestSC302MergeMarkers:
    @pytest.mark.parametrize("line", ["<<<<<<< HEAD", ">>>>>>> branch"])
    def test_angle_markers(self, line):
        diags = list(rule_by_id("SC302").check(skill_doc(body=line + "\n")))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC302"

    def test_equals_marker(self):
        diags = list(rule_by_id("SC302").check(skill_doc(body="=======\n")))
        assert len(diags) == 1

    def test_equals_with_text_not_flagged(self):
        assert list(rule_by_id("SC302").check(skill_doc(body="======= not a marker\n"))) == []

    def test_clean(self):
        assert list(rule_by_id("SC302").check(skill_doc(body="# clean\n"))) == []


class TestSC304TrailingNewline:
    def test_missing_newline_warns(self):
        diags = list(rule_by_id("SC304").check(skill_doc(body="# no newline")))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC304"
        assert diags[0].severity == "warning"

    def test_present_newline_ok(self):
        assert list(rule_by_id("SC304").check(skill_doc(body="# title\n"))) == []

    def test_empty_body_skipped(self):
        # an empty body (or frontmatter-only file) has nothing to terminate
        assert list(rule_by_id("SC304").check(skill_doc(body=""))) == []

    def test_runs_on_skill(self):
        assert len(list(rule_by_id("SC304").check(skill_doc(body="# x")))) == 1

    def test_runs_on_claude(self):
        assert len(list(rule_by_id("SC304").check(claude_doc("CLAUDE.md", body="# x")))) == 1

    def test_runs_on_agents(self):
        assert len(list(rule_by_id("SC304").check(agents_doc(body="# x")))) == 1


def test_valid_skill_passes_all_rules(tmp_path):
    """A well-formed skill in a skills/<name>/ folder triggers no rule."""
    p = tmp_path / "skills" / "good-skill" / "SKILL.md"
    p.parent.mkdir(parents=True)
    doc = skill_doc(
        name="good-skill",
        path=str(p),
        frontmatter={
            "name": "good-skill",
            "description": "A useful skill that performs useful work in the repo.",
        },
        has_frontmatter=True,
        body="# Good skill\n\nDoes useful things.\n",
    )
    assert lint_doc(doc) == []


def _cursor_doc(frontmatter: dict, path: str = ".cursor/rules/x.mdc") -> ConfigDoc:
    return ConfigDoc(
        meta=DocMeta(source_path=Path(path), doc_type="cursor"),
        body="body\n",
        frontmatter=frontmatter,
        has_frontmatter=True,
    )


class TestSC401GlobsValid:
    def test_globs_string_ok(self):
        doc = _cursor_doc({"globs": "**/*.py", "alwaysApply": False})
        assert list(rule_by_id("SC401").check(doc)) == []

    def test_globs_list_ok(self):
        assert list(rule_by_id("SC401").check(_cursor_doc({"globs": ["*.py", "*.pyi"]}))) == []

    def test_always_apply_no_globs_ok(self):
        assert list(rule_by_id("SC401").check(_cursor_doc({"alwaysApply": True}))) == []

    def test_no_globs_no_always_warns(self):
        diags = list(rule_by_id("SC401").check(_cursor_doc({"alwaysApply": False})))
        assert len(diags) == 1
        assert diags[0].rule_id == "SC401"
        assert diags[0].severity == "warning"

    def test_bad_globs_type_errors(self):
        diags = list(rule_by_id("SC401").check(_cursor_doc({"globs": 123})))
        assert len(diags) == 1
        assert diags[0].severity == "error"


class TestSC402AlwaysApplyConflict:
    def test_conflict_warns(self):
        diags = list(
            rule_by_id("SC402").check(_cursor_doc({"alwaysApply": True, "globs": "**/*.py"}))
        )
        assert len(diags) == 1
        assert diags[0].rule_id == "SC402"
        assert diags[0].severity == "warning"

    def test_always_only_ok(self):
        assert list(rule_by_id("SC402").check(_cursor_doc({"alwaysApply": True}))) == []

    def test_globs_only_ok(self):
        assert list(rule_by_id("SC402").check(_cursor_doc({"globs": "**/*.py"}))) == []
