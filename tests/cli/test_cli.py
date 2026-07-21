"""End-to-end CLI tests via Typer's CliRunner."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from skillcraft.cli import app

runner = CliRunner()


def test_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert "skillcraft" in r.stdout
    assert "0.2.1" in r.stdout


def test_init_creates_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["init", "--name", "demo-skill"])
    assert r.exit_code == 0
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".skillcraft.toml").is_file()
    assert "demo-skill" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_init_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    r = runner.invoke(app, ["init", "--name", "demo-skill"])
    assert r.exit_code == 0
    assert "nothing to do" in r.stdout


def test_sync_writes_targets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    r = runner.invoke(app, ["sync"])
    assert r.exit_code == 0
    assert (tmp_path / "SKILL.md").is_file()
    assert (tmp_path / "CLAUDE.md").is_file()
    assert "managed-source" in (tmp_path / "SKILL.md").read_text(encoding="utf-8")


def test_lint_clean_after_sync(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    runner.invoke(app, ["sync"])
    r = runner.invoke(app, ["lint"])
    assert r.exit_code == 0
    assert "No issues found" in r.stdout


def test_sync_check_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    runner.invoke(app, ["sync"])
    r = runner.invoke(app, ["sync", "--check"])
    assert r.exit_code == 0


def test_sync_check_drift_after_mutation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    runner.invoke(app, ["sync"])
    skill = tmp_path / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n# DRIFT\n", encoding="utf-8")
    r = runner.invoke(app, ["sync", "--check"])
    assert r.exit_code == 1
    assert "drifted" in r.stdout


def test_sync_diff_shows_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    runner.invoke(app, ["sync"])
    skill = tmp_path / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n# DRIFT\n", encoding="utf-8")
    r = runner.invoke(app, ["sync", "--diff"])
    assert "# DRIFT" in r.stdout


def test_lint_detects_broken_skill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / ".claude" / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Bad_Name\ndescription: short\n---\n\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["lint"])
    assert r.exit_code == 1
    assert "SC101" in r.stdout
    assert "SC102" in r.stdout
    assert "SC302" in r.stdout


def test_lint_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / ".claude" / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Bad\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    r = runner.invoke(app, ["lint", "--format", "json"])
    assert r.exit_code == 1
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert any(diag["rule_id"] == "SC101" for diag in data)


def test_lint_bogus_format_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    r = runner.invoke(app, ["lint", "--format", "bogus"])
    assert r.exit_code == 2


def test_lint_github_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / ".claude" / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Bad\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    r = runner.invoke(app, ["lint", "--format", "github"])
    assert r.exit_code == 1
    # POSIX paths so GitHub renders clickable PR annotations on every platform
    assert "::error file=.claude/skills/bad/SKILL.md" in r.stdout
    assert "SC101" in r.stdout


def test_lint_sarif_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / ".claude" / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Bad\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    r = runner.invoke(app, ["lint", "--format", "sarif"])
    assert r.exit_code == 1  # SC101 is an error
    doc = json.loads(r.stdout)
    assert doc["version"] == "2.1.0"
    results = doc["runs"][0]["results"]
    assert any(res["ruleId"] == "SC101" and res["level"] == "error" for res in results)
    assert "SC101" in {rule["id"] for rule in doc["runs"][0]["tool"]["driver"]["rules"]}


def test_sync_adopt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo-skill"])
    # a hand-authored, unmanaged SKILL.md (no managed marker)
    (tmp_path / "SKILL.md").write_text("# hand authored\nno marker\n", encoding="utf-8")
    r = runner.invoke(app, ["sync", "--adopt", "SKILL.md"])
    assert r.exit_code == 0
    assert "adopted" in r.stdout
    text = (tmp_path / "SKILL.md").read_text(encoding="utf-8")
    assert "skillcraft:managed-source" in text
    assert "name: demo-skill" in text
