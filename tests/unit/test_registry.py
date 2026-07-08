"""Unit tests for the rule/converter registry and entry-point plugin discovery."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from skillcraft.plugins import registry
from skillcraft.plugins.api import Rule

BUILTIN_RULE_IDS = {"SC101", "SC102", "SC103", "SC104", "SC201", "SC202", "SC301", "SC302"}
BUILTIN_CONVERTERS = {"agents", "skill", "claude"}

_DUMMY_PLUGIN = """
from skillcraft.plugins.api import Rule
from skillcraft.plugins.registry import register_rule


@register_rule
class ExternalRule(Rule):
    id = "SC888"
    formats = ()
    severity = "info"

    def check(self, doc):
        return []
"""


def test_builtins_loaded():
    assert BUILTIN_RULE_IDS.issubset(r.id for r in registry.all_rules())
    assert BUILTIN_CONVERTERS.issubset(c.format_id for c in registry.all_converters())


def test_get_converter_and_for_path():
    assert registry.get_converter("skill").format_id == "skill"
    assert registry.converter_for_path(Path("SKILL.md")).format_id == "skill"
    assert registry.converter_for_path(Path("README.md")) is None


def test_register_rule_requires_id():
    with pytest.raises(ValueError):

        @registry.register_rule
        class NoId(Rule):
            id = ""

            def check(self, doc):
                return []


def test_register_rule_adds_instance(restore_registry):
    @registry.register_rule
    class Dummy(Rule):
        id = "SC999"
        formats = ()
        severity = "info"

        def check(self, doc):
            return []

    assert any(r.id == "SC999" for r in registry.all_rules())


def test_entry_point_discovery(restore_registry, tmp_path, monkeypatch):
    """An external plugin advertised via the skillcraft.rules entry-point is loaded."""
    (tmp_path / "sc_ext_plugin.py").write_text(_DUMMY_PLUGIN, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    ep = EntryPoint("external", "sc_ext_plugin", "skillcraft.rules")

    def fake_entry_points(*, group):
        return [ep] if group == "skillcraft.rules" else []

    monkeypatch.setattr(registry, "entry_points", fake_entry_points)
    monkeypatch.setattr(registry, "_LOADED", False)

    registry.load_plugins()

    ids = {r.id for r in registry.all_rules()}
    assert "SC888" in ids  # external plugin discovered
    assert BUILTIN_RULE_IDS.issubset(ids)  # builtins still present
