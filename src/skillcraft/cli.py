"""skillcraft CLI — Typer wiring only.

All logic lives in ``lint/``, ``sync/``, ``scaffold/`` so it is unit-testable
and importable for embedding in other tools.
"""

from __future__ import annotations

from pathlib import Path

import typer

from skillcraft import __version__
from skillcraft.config import load_config
from skillcraft.discover import discover
from skillcraft.lint import (
    format_github,
    format_json,
    format_plain,
    format_sarif,
    has_errors,
    lint_paths,
)
from skillcraft.plugins.registry import converter_for_path
from skillcraft.scaffold.init import init_repo
from skillcraft.sync import TargetSpec, adopt_target, run_sync

app = typer.Typer(
    name="skillcraft",
    help="ESLint + Jest for agent-config files: lint, sync and scaffold.",
    add_completion=False,
    no_args_is_help=True,
)

_FORMATTERS = {
    "plain": format_plain,
    "json": format_json,
    "github": format_github,
    "sarif": format_sarif,
}


@app.command()
def version() -> None:
    """Print the skillcraft version."""
    typer.echo(f"skillcraft {__version__}")


@app.command()
def lint(
    paths: list[Path] = typer.Argument(  # noqa: B008
        None, help="Files/dirs to lint (default: current directory)."
    ),
    check: bool = typer.Option(  # noqa: B008
        False, "--check", help="Suppress output; exit 1 if any errors (for CI)."
    ),
    fmt: str = typer.Option(  # noqa: B008
        "plain", "--format", "-f", help="Output format: plain|json|github|sarif."
    ),
) -> None:
    """Lint agent-config files against the built-in rules."""
    if fmt not in _FORMATTERS:
        typer.echo(f"unknown format '{fmt}' (use plain|json|github|sarif)", err=True)
        raise typer.Exit(code=2)
    targets: list[Path] = []
    for p in paths or [Path(".")]:
        targets.extend(discover(p) if p.is_dir() else [p])
    diags = lint_paths(targets)
    if not check:
        output = _FORMATTERS[fmt](diags)
        if output:
            typer.echo(output)
    if has_errors(diags):
        raise typer.Exit(code=1)


@app.command()
def sync(
    check: bool = typer.Option(  # noqa: B008
        False, "--check", help="Report drift; exit 1 if any. Never writes (for CI)."
    ),
    diff: bool = typer.Option(  # noqa: B008
        False, "--diff", help="Print unified diffs for drifted targets."
    ),
    adopt: str = typer.Option(  # noqa: B008
        None, "--adopt", help="Path to force-manage (regenerate from canonical)."
    ),
) -> None:
    """Sync the canonical AGENTS.md to managed targets (SKILL.md, CLAUDE.md, etc.)."""
    root = Path.cwd()
    cfg = load_config(root)
    canonical = root / cfg.canonical
    targets = [TargetSpec(t.format_id, root / t.path) for t in cfg.targets]

    if adopt:
        apath = (root / adopt).resolve()
        spec = next((t for t in targets if t.path.resolve() == apath), None)
        if spec is None:
            conv = converter_for_path(apath)
            if conv is None:
                typer.echo(f"cannot adopt '{adopt}': unknown format", err=True)
                raise typer.Exit(code=2)
            spec = TargetSpec(conv.format_id, apath)
        result = adopt_target(canonical, spec)
        for p in result.written:
            typer.echo(f"adopted {p}")
        for msg in result.skipped:
            typer.echo(msg, err=True)
        raise typer.Exit(code=0 if not result.skipped else 1)

    result = run_sync(canonical, targets, check=check, diff=diff)
    for p in result.written:
        typer.echo(f"wrote {p.relative_to(root)}")
    for p in result.unchanged:
        typer.echo(f"ok {p.relative_to(root)}")
    for p in result.drifted:
        typer.echo(f"drifted {p.relative_to(root)}")
    for p in result.unmanaged:
        rel = p.relative_to(root)
        typer.echo(f"unmanaged {rel} (run: skillcraft sync --adopt {rel})")
    for p, text in result.diffs.items():
        typer.echo(f"\n--- diff: {p.relative_to(root)} ---")
        typer.echo(text)
    for msg in result.skipped:
        typer.echo(msg, err=True)
    if check and result.has_drift:
        raise typer.Exit(code=1)


@app.command()
def init(
    name: str = typer.Option(  # noqa: B008
        "my-skill", "--name", help="Skill name (kebab-case) for the scaffold."
    ),
) -> None:
    """Scaffold a minimal canonical AGENTS.md and .skillcraft.toml."""
    written = init_repo(Path.cwd(), name=name)
    if not written:
        typer.echo("nothing to do (AGENTS.md and .skillcraft.toml already exist)")
        return
    for p in written:
        typer.echo(f"created {p}")
    typer.echo("\nNext: edit AGENTS.md, then run `skillcraft sync`.")


if __name__ == "__main__":
    app()
