## What

<!-- one sentence: what does this PR add or fix? -->

## Rule / converter ID

<!-- e.g. SC106 (new SKILL rule) / windsurf converter / docs / n/a -->

## Checklist

- [ ] `uv run ruff check` and `uv run ruff format --check` pass
- [ ] `uv run pytest` passes (added a test for the new rule / converter)
- [ ] `uv run skillcraft lint` reports no issues on this repo
- [ ] `uv run skillcraft sync --check` is clean — or, if I edited `AGENTS.md`, I ran `uv run skillcraft sync` and committed the regenerated `SKILL.md` / `CLAUDE.md`
- [ ] rule ID follows the taxonomy and is not already taken
