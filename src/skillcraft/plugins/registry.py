"""Rule/converter registry with entry-point plugin discovery.

Built-ins self-register on import (via the decorators). External plugins are
discovered through the ``skillcraft.rules`` / ``skillcraft.converters``
entry-point groups (ruff/pytest style).

A broken external plugin is swallowed (it must never kill the tool), and an
external plugin that reuses a built-in id is refused — built-ins always win, so
a third-party rule/converter cannot silently disable a built-in.
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points
from pathlib import Path

from skillcraft.plugins.api import Converter, Rule

_RULES: dict[str, Rule] = {}
_CONVERTERS: dict[str, Converter] = {}
# IDs claimed by built-ins, snapshotted once after the built-in modules import.
# Lets register_* refuse an external plugin that tries to shadow a built-in.
_BUILTIN_RULE_IDS: set[str] = set()
_BUILTIN_CONVERTER_IDS: set[str] = set()
_LOADED = False


def _warn_shadow(kind: str, ident: str, cls_name: str) -> None:
    print(
        f"skillcraft: {kind} {ident!r} from {cls_name!r} shadows a built-in; keeping the built-in.",
        file=sys.stderr,
    )


def register_rule(cls: type[Rule]) -> type[Rule]:
    """Class decorator: instantiate and register a Rule by its ``id``."""
    instance = cls()
    if not instance.id:
        msg = f"{cls.__name__}: Rule.id must be set"
        raise ValueError(msg)
    if instance.id in _RULES and instance.id in _BUILTIN_RULE_IDS:
        _warn_shadow("rule", instance.id, cls.__name__)
        return cls
    _RULES[instance.id] = instance
    return cls


def register_converter(cls: type[Converter]) -> type[Converter]:
    """Class decorator: instantiate and register a Converter by its ``format_id``."""
    instance = cls()
    if not instance.format_id:
        msg = f"{cls.__name__}: Converter.format_id must be set"
        raise ValueError(msg)
    if instance.format_id in _CONVERTERS and instance.format_id in _BUILTIN_CONVERTER_IDS:
        _warn_shadow("converter", instance.format_id, cls.__name__)
        return cls
    _CONVERTERS[instance.format_id] = instance
    return cls


def all_rules() -> list[Rule]:
    return list(_RULES.values())


def all_converters() -> list[Converter]:
    return list(_CONVERTERS.values())


def get_converter(format_id: str) -> Converter | None:
    return _CONVERTERS.get(format_id)


def converter_for_path(path: Path) -> Converter | None:
    """Pick the converter that claims a given path (by ``applies_to``)."""
    for converter in _CONVERTERS.values():
        if converter.applies_to(path):
            return converter
    return None


def load_plugins() -> None:
    """Import built-ins (self-register) and load external entry-point plugins.

    Idempotent: safe to call repeatedly.
    """
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    # Built-ins register themselves on import.
    from skillcraft.plugins.builtin import converters as _converters  # noqa: F401
    from skillcraft.plugins.builtin import rules as _rules  # noqa: F401

    # Snapshot built-in ids so external plugins can be refused if they reuse one.
    _BUILTIN_RULE_IDS.update(_RULES)
    _BUILTIN_CONVERTER_IDS.update(_CONVERTERS)

    for group in ("skillcraft.rules", "skillcraft.converters"):
        for ep in entry_points(group=group):
            try:
                ep.load()
            except Exception:  # noqa: BLE001 — a broken plugin must not kill the tool
                continue
