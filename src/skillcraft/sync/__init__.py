"""Sync engine: canonical AGENTS.md → managed targets, with drift detection."""

from skillcraft.sync.engine import (
    SyncResult,
    TargetSpec,
    adopt_target,
    render_target,
    run_sync,
)

__all__ = ["SyncResult", "TargetSpec", "adopt_target", "render_target", "run_sync"]
