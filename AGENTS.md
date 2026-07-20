<!-- skillcraft:meta {"name":"skillcraft","description":"Lint, sync and scaffold agent-config files (SKILL.md, CLAUDE.md, AGENTS.md). Use when checking, validating or regenerating agent-config files in a repository."} -->

# skillcraft

**ESLint + Jest for agent-config files.** `skillcraft` lints, syncs and scaffolds the fragmented ecosystem of `SKILL.md`, `CLAUDE.md`, `AGENTS.md` (and, in v0.2, `.cursor/rules`, `.claude/rules`, copilot-instructions). One canonical source, many managed targets, drift detection in CI.

## Install

```bash
uv tool install skillcraft
# or: pip install skillcraft
```

## Commands

| Command | Purpose |
| --- | --- |
| `skillcraft lint [--check] [-f plain\|json\|github]` | Run the rule set over discovered config files; exit 1 on any ERROR. |
| `skillcraft sync [--check] [--diff] [--adopt <file>]` | Regenerate managed targets from `AGENTS.md`; detect drift. |
| `skillcraft init [--name <name>]` | Scaffold a minimal `AGENTS.md` + `.skillcraft.toml`. |
| `skillcraft version` | Print the version. |

## How it works

- **Canonical source = `AGENTS.md`** (vendor-neutral, schema-less). Richer metadata (name, description, scope, license, …) rides in invisible `<!-- skillcraft:meta <json> -->` comments — valid markdown to every consumer, machine-readable to `skillcraft`.
- **IR: `ConfigDoc`.** Every parser emits it, every renderer consumes it. Same-format parse→render is lossless; `extra_frontmatter` escape hatch guarantees no field is silently dropped.
- **Sync.** `skillcraft sync` renders each target from the canonical doc and writes it with a `<!-- skillcraft:managed-source path=AGENTS.md sha=… -->` marker. `skillcraft sync --check` exits 1 if any managed target drifted (CI). Unmanaged files are never overwritten; opt in with `--adopt`.
- **Plugins.** Subclass `Rule` or `Converter`, decorate with `@register_rule` / `@register_converter`, and (for external packages) declare an entry-point in `skillcraft.rules` / `skillcraft.converters`. See `CONTRIBUTING.md`.

## Rules

| ID | Scope | Rule |
| --- | --- | --- |
| SC101 | SKILL | `name` is kebab-case, ≤64 chars |
| SC102 | SKILL | in a `skills/<name>/` folder, `name` matches the folder |
| SC103 | SKILL | `description` present, ≤1024 chars |
| SC104 | SKILL | body ≈ <5000 tokens (warn past 4000) |
| SC201 | CLAUDE | `@path` imports resolve, no cycles, ≤4 hops |
| SC202 | CLAUDE | line count <200 (warn), <500 (error) |
| SC301 | ALL | required frontmatter present iff the format requires it |
| SC302 | ALL | no merge-conflict markers in the body |
| SC401 | CURSOR | globs well-formed and the rule is reachable (error/warn) |
| SC402 | CURSOR | not both `alwaysApply: true` and `globs` (warn) |

## Build & test

```bash
uv sync
uv run ruff check
uv run pytest
uv run skillcraft lint          # dogfood: lint skillcraft's own configs
uv run skillcraft sync --check  # dogfood: no drift between AGENTS.md and targets
```

## Layout

```
src/skillcraft/   cli, ir, markers, tokens, config, discover
                  lint/{runner,report}  sync/engine  scaffold/init
                  plugins/{api,registry,builtin/{rules,converters}}
tests/            unit (ir, markers, rules, converters, sync, registry, config, discover) + cli e2e
```

## License

MIT.
