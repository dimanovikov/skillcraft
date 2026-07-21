# Architecture

This document explains the design decisions behind `skillcraft` — the data model, the sync semantics, and the plugin contract. It is the reference for contributors touching `ir.py`, the converters, the sync engine, or the plugin API.

## Goals

1. Solve a real, felt pain: agent-config files (`SKILL.md`, `CLAUDE.md`, `AGENTS.md`) that silently fail to load, get copy-pasted and drift across tools, with no way to test a change.
2. Be a credible, plugin-friendly OSS tool — every additional rule or format should be a one-file contribution with no core changes.

Non-goals for v0.1: live model evaluation (v2), autofix (v1.0), reverse-direction sync (v1.0).

## The canonical source: `AGENTS.md`

`AGENTS.md` is a vendor-neutral, schema-less, open standard. A schema-less format can *absorb* richer metadata, so it is the only choice that does not take a vendor's side. Richer formats' capabilities (frontmatter, globs, name/description, scope) are carried through `AGENTS.md` via invisible HTML-comment extensions — valid markdown to every existing consumer, machine-readable to `skillcraft`.

## Intermediate representation: `ConfigDoc`

Every parser emits a `ConfigDoc`; every renderer consumes one. Plain dataclasses (no Pydantic in v0.1 — minimal deps).

```
ConfigDoc
├─ meta: DocMeta                  # identity + scoping, all optional except source/type
│   ├─ source_path, doc_type      # agents | claude | skill | cursor | copilot
│   ├─ name, description          # skill name/trigger
│   ├─ scope_globs, scope_file_types
│   ├─ license, compatibility, allowed_tools
│   └─ extra_frontmatter          # anything unmodelled — PRESERVED, never dropped
├─ imports: list[ImportRef]       # @path refs (CLAUDE.md, skill body)
├─ sections: list[Section]        # heading / level / body
├─ frontmatter / frontmatter_raw  # parsed dict + verbatim YAML for lossless render
├─ has_frontmatter / frontmatter_error
└─ diagnostics: list[Diagnostic]
```

**Invariants:**

- The IR is format-agnostic — the *union* of all formats' fields.
- Each format's parse → IR → render is **lossless for that same format** (enforced by fixture tests). `frontmatter_raw` (verbatim) is replayed on same-format render; `extra_frontmatter` preserves any key we do not model. This is a trust requirement: `skillcraft` must never silently destroy a field.

## Converter matrix

| Format | parse | render | v0.1? |
| --- | :--: | :--: | :--: |
| `AGENTS.md` | ✅ | ✅ (canonical) | v0.1 |
| `SKILL.md` | ✅ | ✅ | v0.1 |
| `CLAUDE.md` | ✅ | ✅ | v0.1 |
| `.cursor/rules/*.mdc` | ✅ | ✅ | v0.2 |
| `.claude/rules/*.md` | ✅ | ✅ | v0.2 |
| `.github/copilot-instructions.md` | ✅ | ✅ | v0.2 |
| legacy `.cursorrules` | parse-only (+migrate) | — | v0.2 |

## Capability-mismatch decision table

When a target format cannot natively express a field, the action is fixed (no per-format ad-hoc choices). The universal extension channel is the HTML comment:

```
<!-- skillcraft:meta    <json> -->   carried metadata (name, description, …)
<!-- skillcraft:scope   <json> -->   scope_globs a target can't express natively
<!-- skillcraft:managed-source path=… -->  marks a sync-managed target
```

| Target can't express | Action |
| --- | --- |
| `name` (SKILL-only) | drop silently (names are filesystem-derived elsewhere) |
| `description` (SKILL/Cursor) | warn (loses triggerability); emit a `skillcraft:` comment so it survives round-trip |
| `scope_globs` (Cursor/.claude/rules) | annotate as `<!-- skillcraft:scope … -->` |
| `imports` (CLAUDE-only) | inline the imported body at `@path`; warn it was flattened |
| unknown `extra_frontmatter` | always preserve in `<!-- skillcraft:meta … -->` |

## Sync semantics

```
skillcraft sync            # regenerate managed targets; skip unmanaged ones
skillcraft sync --check    # report drift; never write (CI)
skillcraft sync --diff     # unified diffs for drifted targets
skillcraft sync --adopt F  # force-manage a target (overwrite from canonical)
```

- **Determinism.** Renderers MUST be deterministic (sorted keys, stable order) — enforced by property tests. Without it, `--check` flakes and loses trust.
- **Managed marker.** A target is "managed" iff it contains `<!-- skillcraft:managed-source path=AGENTS.md -->`. Unmanaged files are never overwritten.
- **Drift detection.** Drift = the on-disk content (marker stripped) differs from a fresh render. The engine compares content (not a stored hash) so it catches target-side hand-edits as well as canonical changes — drift in *both* directions. Line endings are stable because `.gitattributes` enforces `eol=lf`.
- **Round-trip.** Target → source is out of scope until v1.0, and only as a one-way `--reverse` promotion, not continuous sync.

## Plugin API

Public, semver-stable surface in `src/skillcraft/plugins/api.py`:

```python
class Rule:
    id: str
    formats: tuple[str, ...] = ()   # () = all formats
    severity: str = "error"
    def check(self, doc: ConfigDoc) -> Iterable[Diagnostic]: ...
    def fix(self, doc: ConfigDoc) -> ConfigDoc | None: ...   # optional autofix

class Converter:
    format_id: str
    def applies_to(self, path) -> bool: ...
    def parse(self, path, text: str) -> ConfigDoc: ...
    def render(self, doc: ConfigDoc) -> str: ...
```

Built-ins self-register via `@register_rule` / `@register_converter`. `load_plugins()` (idempotent) then pulls external plugins through the `skillcraft.rules` / `skillcraft.converters` entry-point groups (ruff/pytest style). A broken plugin is swallowed — it must never kill the tool.

`plugins/api.py` is the API stability gate: changes there are semver-sensitive (see `CODEOWNERS`).

## Rule taxonomy

IDs are `SCxxx`, greppable, and never renumbered:

- `SC1xx` — `SKILL.md`
- `SC2xx` — `CLAUDE.md`
- `SC3xx` — universal (all formats)
- `SC4xx` — `.cursor` rules (v0.2)

## Module layout

```
src/skillcraft/
├─ cli.py            # Typer wiring ONLY — no logic
├─ ir.py             # ConfigDoc / DocMeta / parsing helpers (highest-leverage file)
├─ markers.py        # skillcraft:* HTML-comment conventions
├─ tokens.py         # heuristic token estimate
├─ config.py         # .skillcraft.toml loading
├─ discover.py       # walk a tree, find files a converter claims
├─ lint/{runner,report}.py
├─ sync/engine.py    # drift detection + managed-marker writes
├─ scaffold/init.py
└─ plugins/{api,registry,builtin/{rules,converters}}.py
```

`cli.py` holds no logic — commands delegate to `lint/runner.py` and `sync/engine.py`, so `run_lint()` / `run_sync()` are importable and unit-testable, and embeddable in other tools.
