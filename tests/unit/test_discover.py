"""Unit tests for config-file discovery."""

from __future__ import annotations

from skillcraft.discover import discover


def test_discovers_config_files_and_skips_noise(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "SKILL.md").write_text("# should be skipped\n", encoding="utf-8")

    found = [p.name for p in discover(tmp_path)]
    assert "AGENTS.md" in found
    assert "SKILL.md" in found
    assert "README.md" not in found
    assert found.count("SKILL.md") == 1  # .venv entry skipped


def test_discover_single_file(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# x\n", encoding="utf-8")
    assert discover(agents) == [agents]


def test_discover_unknown_file_yields_empty(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# x\n", encoding="utf-8")
    assert discover(readme) == []
