"""Unit tests for per-repo config loading."""

from __future__ import annotations

from skillcraft.config import default_targets, load_config


def test_default_targets():
    t = default_targets()
    assert [s.format_id for s in t] == ["skill", "claude"]


def test_load_config_defaults_when_absent(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.canonical == "AGENTS.md"
    assert [s.format_id for s in cfg.targets] == ["skill", "claude"]


def test_load_config_reads_toml(tmp_path):
    (tmp_path / ".skillcraft.toml").write_text(
        '[sync]\ncanonical = "AGENTS.md"\n'
        '[[sync.targets]]\nformat = "claude"\npath = "CLAUDE.md"\n',
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.canonical == "AGENTS.md"
    assert [(t.format_id, str(t.path)) for t in cfg.targets] == [("claude", "CLAUDE.md")]


def test_load_config_malformed_falls_back(tmp_path):
    (tmp_path / ".skillcraft.toml").write_text("this is = = not valid {{{", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.canonical == "AGENTS.md"
    assert len(cfg.targets) == 2
