"""Public, semver-stable plugin API.

Contributors subclass :class:`Rule` or :class:`Converter`, decorate with
``@register_rule`` / ``@register_converter``, and (for external packages)
declare an entry-point in ``pyproject.toml``. That is the entire contract —
see ``docs/plugin-guide.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from skillcraft.ir import ConfigDoc, Diagnostic

__all__ = ["Rule", "Converter", "Diagnostic", "ConfigDoc"]


class Rule:
    """A lint rule. Subclass, set ``id``/``formats``/``severity``, implement ``check``."""

    id: str = ""
    formats: tuple[str, ...] = ()  # () = applies to all formats
    severity: str = "error"
    description: str = ""

    def check(self, doc: ConfigDoc) -> Iterable[Diagnostic]:  # noqa: ARG002
        return []

    def fix(self, doc: ConfigDoc) -> ConfigDoc | None:  # noqa: ARG002
        """Optional autofix. Return a new doc, or None if not fixable."""
        return None


class Converter:
    """A format parser + renderer. Subclass, set ``format_id``, implement the trio."""

    format_id: str = ""

    def applies_to(self, path: Path) -> bool:  # noqa: ARG002
        return False

    def parse(self, path: Path, text: str) -> ConfigDoc:  # noqa: ARG002
        raise NotImplementedError

    def render(self, doc: ConfigDoc) -> str:  # noqa: ARG002
        raise NotImplementedError
