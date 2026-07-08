"""Parametrized unit tests for the built-in lint rules (SC101–SC302)."""

from __future__ import annotations

import pytest

from skillcraft.ir import ImportRef, find_imports
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


def test_valid_skill_passes_all_rules(tmp_path):
    """A well-formed skill in a skills/<name>/ folder triggers no rule."""
    p = tmp_path / "skills" / "good-skill" / "SKILL.md"
    p.parent.mkdir(parents=True)
    doc = skill_doc(
        name="good-skill",
        path=str(p),
        frontmatter={"name": "good-skill", "description": "A useful skill."},
        has_frontmatter=True,
        body="# Good skill\n\nDoes useful things.\n",
    )
    assert lint_doc(doc) == []
