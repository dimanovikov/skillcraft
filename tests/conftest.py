"""Shared fixtures for the skillcraft test suite."""

from __future__ import annotations

import pytest

from skillcraft.plugins import registry


@pytest.fixture(scope="session", autouse=True)
def _load_builtins() -> None:
    """Register built-in rules/converters once for the whole session."""
    registry.load_plugins()


@pytest.fixture
def restore_registry():
    """Snapshot and restore the global registry (for plugin-registration tests)."""
    snap_rules = dict(registry._RULES)
    snap_converters = dict(registry._CONVERTERS)
    snap_loaded = registry._LOADED
    yield
    registry._RULES.clear()
    registry._RULES.update(snap_rules)
    registry._CONVERTERS.clear()
    registry._CONVERTERS.update(snap_converters)
    registry._LOADED = snap_loaded
