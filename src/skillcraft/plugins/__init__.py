"""Plugin system: public API + registry."""

from skillcraft.plugins.api import Converter, Diagnostic, Rule
from skillcraft.plugins.registry import (
    all_converters,
    all_rules,
    converter_for_path,
    get_converter,
    load_plugins,
    register_converter,
    register_rule,
)

__all__ = [
    "Rule",
    "Converter",
    "Diagnostic",
    "register_rule",
    "register_converter",
    "all_rules",
    "all_converters",
    "get_converter",
    "converter_for_path",
    "load_plugins",
]
