"""Heuristic token estimation — no model dependency, good enough for size warnings."""

from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 characters per token)."""
    return math.ceil(len(text) / 4)
