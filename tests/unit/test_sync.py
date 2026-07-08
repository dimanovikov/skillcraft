"""Unit tests for the sync engine: write / check / drift / diff / adopt / determinism."""

from __future__ import annotations

from skillcraft.sync import TargetSpec, adopt_target, run_sync

AGENTS = (
    '<!-- skillcraft:meta {"name":"demo-skill","description":"A demo skill."} -->\n\n'
    "# demo-skill\n\nBody.\n"
)


def _setup(tmp_path):
    (tmp_path / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
    targets = [
        TargetSpec("skill", tmp_path / "SKILL.md"),
        TargetSpec("claude", tmp_path / "CLAUDE.md"),
    ]
    return tmp_path / "AGENTS.md", targets


class TestRunSync:
    def test_write_creates_managed_targets(self, tmp_path):
        canon, targets = _setup(tmp_path)
        r = run_sync(canon, targets)
        assert r.written == [tmp_path / "SKILL.md", tmp_path / "CLAUDE.md"]
        skill = (tmp_path / "SKILL.md").read_text(encoding="utf-8")
        assert skill.startswith("<!-- skillcraft:managed-source")
        assert "---\nname: demo-skill" in skill

    def test_check_clean_after_write(self, tmp_path):
        canon, targets = _setup(tmp_path)
        run_sync(canon, targets)
        r = run_sync(canon, targets, check=True)
        assert not r.has_drift
        assert r.unchanged == [tmp_path / "SKILL.md", tmp_path / "CLAUDE.md"]

    def test_drift_detected_on_target_edit(self, tmp_path):
        canon, targets = _setup(tmp_path)
        run_sync(canon, targets)
        skill = tmp_path / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n\n# HAND EDIT\n", encoding="utf-8")
        r = run_sync(canon, targets, check=True, diff=True)
        assert r.has_drift
        assert skill in r.drifted
        assert skill in r.diffs
        assert "# HAND EDIT" in r.diffs[skill]

    def test_rewrite_after_drift(self, tmp_path):
        canon, targets = _setup(tmp_path)
        run_sync(canon, targets)
        skill = tmp_path / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n# EDIT\n", encoding="utf-8")
        r = run_sync(canon, targets)  # no check → rewrites drifted target
        assert skill in r.written
        assert run_sync(canon, targets, check=True).has_drift is False

    def test_unmanaged_target_skipped(self, tmp_path):
        canon, targets = _setup(tmp_path)
        # pre-existing hand-authored SKILL.md with no managed marker
        (tmp_path / "SKILL.md").write_text(
            "---\nname: x\ndescription: y\n---\nbody\n", encoding="utf-8"
        )
        r = run_sync(canon, targets)
        assert tmp_path / "SKILL.md" in r.unmanaged
        assert tmp_path / "SKILL.md" not in r.written

    def test_missing_canonical_skipped(self, tmp_path):
        targets = [TargetSpec("skill", tmp_path / "SKILL.md")]
        r = run_sync(tmp_path / "AGENTS.md", targets)
        assert r.skipped
        assert not r.written

    def test_two_syncs_produce_identical_bytes(self, tmp_path):
        canon, targets = _setup(tmp_path)
        run_sync(canon, targets)
        first_skill = (tmp_path / "SKILL.md").read_text(encoding="utf-8")
        first_claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        run_sync(canon, targets)  # idempotent rewrite
        assert (tmp_path / "SKILL.md").read_text(encoding="utf-8") == first_skill
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == first_claude


class TestAdoptTarget:
    def test_adopt_manages_unmanaged(self, tmp_path):
        canon, _ = _setup(tmp_path)
        skill = tmp_path / "SKILL.md"
        skill.write_text("# hand authored, no marker\n", encoding="utf-8")
        r = adopt_target(canon, TargetSpec("skill", skill))
        assert skill in r.written
        text = skill.read_text(encoding="utf-8")
        assert "skillcraft:managed-source" in text
        assert "---\nname: demo-skill" in text


def test_sync_skips_skill_when_canonical_lacks_meta(tmp_path):
    # AGENTS.md with no name/description meta cannot build a SKILL.md
    (tmp_path / "AGENTS.md").write_text("# just docs, no meta\n", encoding="utf-8")
    targets = [
        TargetSpec("skill", tmp_path / "SKILL.md"),
        TargetSpec("claude", tmp_path / "CLAUDE.md"),
    ]
    r = run_sync(tmp_path / "AGENTS.md", targets)
    assert tmp_path / "SKILL.md" not in r.written  # skipped
    assert tmp_path / "CLAUDE.md" in r.written  # claude needs no meta
    assert r.skipped


def test_adopt_returns_skip_when_cannot_render(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# no meta\n", encoding="utf-8")
    r = adopt_target(tmp_path / "AGENTS.md", TargetSpec("skill", tmp_path / "SKILL.md"))
    assert r.skipped
    assert not r.written
