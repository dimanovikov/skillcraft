"""Unit tests for the heuristic token estimator."""

from __future__ import annotations

from skillcraft.tokens import estimate_tokens


def test_empty():
    assert estimate_tokens("") == 0


def test_rounds_up():
    assert estimate_tokens("abcde") == 2  # ceil(5/4)


def test_exact_multiple():
    assert estimate_tokens("abcd") == 1  # ceil(4/4)
