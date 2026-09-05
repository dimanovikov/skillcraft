# Contributing to skillcraft

Thanks for your interest! `skillcraft` is built to be extended — most contributions are a **single new file** (a rule or a converter) with **zero core changes**. That's by design: the contributor experience *is* the product.

> Every rule spec'd in [ARCHITECTURE.md](ARCHITECTURE.md) but not yet implemented is an open [good-first-issue](https://github.com/dimanovikov/skillcraft/contribute). Grab one.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/dimanovikov/skillcraft.git
cd skillcraft
uv sync            # creates .venv, installs dev deps
uv run pytest      # 120+ tests, <1s
uv run ruff check
```

## Layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data model. The short version:

- `src/skillcraft/ir.py` — `ConfigDoc`, the format-agnostic IR.
- `src/skillcraft/plugins/api.py` — **the semver-stable public surface**; changes here are versioned (see [CODEOWNERS](CODEOWNERS)).
- `src/skillcraft/plugins/builtin/{rules,converters}.py` — built-ins, self-registered via decorators.
- `src/skillcraft/sync/engine.py` — drift detection + managed-marker writes.
- `tests/` — unit tests (one file per module) + CLI e2e.

`cli.py` holds no logic — it delegates to `lint/runner.py` and `sync/engine.py`, so `run_lint()` / `run_sync()` are importable and unit-testable.

## Add a rule

1. Pick an ID from the [taxonomy](ARCHITECTURE.md#rule-taxonomy): `SC1xx` SKILL, `SC2xx` CLAUDE, `SC3xx` universal, `SC4xx` cursor. IDs are stable and **never renumbered** — check the existing rules table in [README.md](README.md) so you don't collide.
2. Subclass `Rule` and decorate it:

```python
# my_plugin/rules.py  (or src/skillcraft/plugins/builtin/rules.py for a built-in)
from skillcraft.plugins.api import Diagnostic, Rule
from skillcraft.plugins.registry import register_rule

@register_rule
class SkillNameUppercase(Rule):
    id = "SC106"
    formats = ("skill",)
    severity = "error"

    def check(self, doc):
        if doc.meta.name and doc.meta.name != doc.meta.name.lower():
            yield Diagnostic(
                self.id, self.severity,
                f"skill name '{doc.meta.name}' must be lowercase",
                str(doc.meta.source_path),
            )
```

3. **If built-in:** add a parametrized test in `tests/unit/test_rules.py` — one valid case (no diagnostic) and one invalid case (diagnostic with the expected message). **If external package:** declare the entry-point in your `pyproject.toml`:

```toml
[project.entry-points."skillcraft.rules"]
my_rules = "my_plugin.rules"
```

That's it — `skillcraft lint` discovers and runs it automatically. Zero core changes.

## Add a converter (a new format)

Same shape, `skillcraft.converters` group:

```python
from pathlib import Path
from skillcraft.plugins.api import ConfigDoc, Converter
from skillcraft.plugins.registry import register_converter

@register_converter
class WindsurfConverter(Converter):
    format_id = "windsurf"

    def applies_to(self, path: Path) -> bool:
        return ".windsurf" in path.parts and path.suffix == ".md"

    def parse(self, path, text) -> ConfigDoc: ...
    def render(self, doc: ConfigDoc) -> str: ...
```

Two contracts:

- `parse` populates a `ConfigDoc`; `render` consumes one.
- `render` MUST be **deterministic** (sorted keys, stable order) or `sync --check` flakes. Same-format parse→render must be **lossless** — add a round-trip test (see `tests/unit/test_converters.py`).

## Before you open a PR

The project dogfoods itself — CI fails if the repo's own configs drift or violate a rule. Locally:

```bash
uv run ruff check && uv run ruff format --check
uv run pytest
uv run skillcraft lint          # must report "No issues found"
uv run skillcraft sync --check  # must be clean (no drift)
```

If you edited `AGENTS.md`, regenerate the managed targets and commit them too:

```bash
uv run skillcraft sync          # rewrites SKILL.md + CLAUDE.md
```

Keep PRs scoped to **one rule or one converter** — they're easy to review and easy to credit in the changelog. The PR template asks for the ID and a one-line acceptance test.

## Commit style

Conventional-ish, not enforced: `feat(rule): SC106 skill name must be lowercase`, `fix(sync): detect target-side edits`, `feat(converter): windsurf rules`. Helpful in the changelog, that's all.

## Code of Conduct

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Be kind.
