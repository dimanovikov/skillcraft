# skillcraft

[![CI](https://github.com/cloudroad-io/skillcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/cloudroad-io/skillcraft/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/skillcraft.svg)](https://pypi.org/project/skillcraft/)
[![Python](https://img.shields.io/pypi/pyversions/skillcraft.svg)](https://pypi.org/project/skillcraft/)
[![License: MIT](https://img.shields.io/pypi/l/skillcraft.svg)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](.pre-commit-config.yaml)
[![self-lint](https://img.shields.io/badge/skillcraft-lint%20clean-brightgreen)](#dogfooding)

**ESLint + Jest for agent-config files.** `skillcraft` lints, syncs and scaffolds the fragmented ecosystem of `SKILL.md`, `CLAUDE.md` and `AGENTS.md` — one canonical source, many managed targets, drift detection in CI.

> Agent-config files are copy-pasted, drift apart across tools, and silently fail to load. `skillcraft` gives them the same lint/test/sync workflow that code already enjoys.

## 30-second tour

```bash
uv tool install skillcraft      # or: pip install skillcraft
cd your-repo
skillcraft init --name my-skill # writes a canonical AGENTS.md + .skillcraft.toml
# ...edit AGENTS.md...
skillcraft sync                 # generates managed SKILL.md + CLAUDE.md
skillcraft lint                 # validates every agent-config file in the repo
```

In CI, lock it down:

```bash
skillcraft sync --check   # exit 1 if SKILL.md/CLAUDE.md drifted from AGENTS.md
skillcraft lint --check   # exit 1 on any ERROR; --format=github annotates the PR
```

## Why

- **One source of truth.** Write `AGENTS.md` once; `skillcraft sync` regenerates `SKILL.md` and `CLAUDE.md`. Edit a target by hand and `sync --check` catches the drift.
- **Lint that knows the formats.** Kebab-case names, frontmatter presence, import cycles, token budgets, merge-conflict markers — see [the rule table](#rules-v01).
- **PR annotations.** `--format=github` emits `::error file=…,line=…::…` so findings render inline on pull requests. `--format=sarif` emits a SARIF 2.1.0 report for GitHub's **Security → Code scanning** (upload with `github/codeql-action/upload-sarif`).
- **Plugin-friendly.** Add a rule or a format converter in one file, no core changes. See [Contributing](CONTRIBUTING.md).

## Commands

| Command | Purpose |
| --- | --- |
| `skillcraft lint [--check] [-f plain\|json\|github\|sarif]` | Run the rule set over discovered config files; exit 1 on any ERROR. |
| `skillcraft sync [--check] [--diff] [--adopt <file>]` | Regenerate managed targets from `AGENTS.md`; detect or rewrite drift. |
| `skillcraft init [--name <name>]` | Scaffold a minimal `AGENTS.md` + `.skillcraft.toml`. |
| `skillcraft version` | Print the version. |

## Rules (v0.1)

| ID | Scope | Rule | Severity |
| --- | --- | --- | --- |
| SC101 | SKILL | `name` is kebab-case, ≤64 chars | error |
| SC102 | SKILL | in a `skills/<name>/` folder, `name` matches the folder | error |
| SC103 | SKILL | `description` present, ≤1024 chars | error |
| SC104 | SKILL | body ≈ <5000 tokens | warn |
| SC105 | SKILL | `description` ≥40 chars (triggerability) | warn |
| SC201 | CLAUDE | `@path` imports resolve, no cycles, ≤4 hops | error/warn |
| SC202 | CLAUDE | line count <200 (warn), <500 (error) | warn/error |
| SC301 | ALL | required frontmatter present iff the format requires it | error |
| SC302 | ALL | no merge-conflict markers in the body | error |
| SC304 | ALL | body ends with a trailing newline | warn |

Rule IDs are stable and never renumbered — `SC1xx` = SKILL, `SC2xx` = CLAUDE, `SC3xx` = universal, `SC4xx` = `.cursor` (v0.2). Every spec'd rule not yet implemented is an open [good-first-issue](https://github.com/cloudroad-io/skillcraft/contribute).

## How it works

`AGENTS.md` is the **canonical source** — vendor-neutral, schema-less. Richer metadata (name, description, scope, license, …) rides in invisible HTML comments that every markdown consumer ignores but `skillcraft` reads:

```markdown
<!-- skillcraft:meta {"name":"my-skill","description":"…"} -->

# my-skill
…
```

Every format parses into a single `ConfigDoc` IR and renders back out. Same-format parse→render is **lossless**; an `extra_frontmatter` escape hatch guarantees no field is ever silently dropped. Managed targets carry a marker:

```markdown
<!-- skillcraft:managed-source path=AGENTS.md -->
```

`sync --check` compares each managed target against a fresh render and fails CI on any difference. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full model.

## Plugins

```python
from skillcraft.plugins.api import Rule, Diagnostic
from skillcraft.plugins.registry import register_rule

@register_rule
class SkillNameLength(Rule):
    id = "SC101"
    formats = ("skill",)
    severity = "error"

    def check(self, doc):
        if doc.meta.name and len(doc.meta.name) > 64:
            yield Diagnostic(self.id, self.severity, "skill name >64 chars",
                             str(doc.meta.source_path))
```

Ship it as a package with one entry-point — `skillcraft lint` discovers and runs it automatically:

```toml
[project.entry-points."skillcraft.rules"]
my_rules = "my_plugin.rules"
```

Converters (new formats) use the identical shape under the `skillcraft.converters` group. Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

<a name="dogfooding"></a>
## Dogfooding

`skillcraft` is its own first user. This repo's `SKILL.md` and `CLAUDE.md` are **generated** from [`AGENTS.md`](AGENTS.md) by `skillcraft sync`, and CI runs `skillcraft lint --check` + `skillcraft sync --check` on every push — if the project's own configs drift or violate a rule, the build fails.

## Roadmap

- **v0.1** — lint (8 rules, 3 formats) + sync + init + version + `--format=github`. Plugin API frozen. *(this release)*
- **v0.2** — `.cursor/rules`, `.claude/rules`, copilot-instructions, legacy `.cursorrules` migration; static `test` (fixture-based, no model calls); autofix for SC101/SC102.
- **v1.0** — semver-frozen API, `--fix` everywhere, `skillcraft doctor`, pre-commit hook, `--reverse` promotion, PyPI trusted publishing.
- **v2** — live model evals (`skillcraft test --eval`).

## Contributing

PRs welcome — especially new rules and format converters (each is a self-contained good-first-issue). See [CONTRIBUTING.md](CONTRIBUTING.md) and [ARCHITECTURE.md](ARCHITECTURE.md). By contributing you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
