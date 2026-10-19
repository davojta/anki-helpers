# Design: Migrate from Poetry to uv

Tier: medium · Date: 2026-10-19 · Proposal: [proposal.md](proposal.md)

## Data flow

```
pyproject.toml → [uv lock] → uv.lock → [uv sync --locked] → .venv → [uv run …] → pytest / pre-commit / anki-helpers
```

| # | Component | In | Transform | Out |
|---|-----------|----|-----------|-----|
| 1 | `pyproject.toml` | — | PEP 621 metadata, lower-bound deps, `dev` group, hatchling backend | project spec |
| 2 | `uv lock` | project spec | fresh resolution for `>=3.14` | `uv.lock` |
| 3 | `uv sync --locked` | `uv.lock` | create `.venv`, install deps + `dev` group + project (editable) | `.venv` |
| 4 | `uv run` | `.venv` | run tools / `anki-helpers` entry point | test + lint results |

## Types: critical path

No Python code changes. Config changes only.

`pyproject.toml` after:

```toml
[project]
name = "anki-helpers"
version = "0.1.0"
description = "A CLI tool to help with Anki flashcards"
authors = [{ name = "davojta" }]
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "click>=8.1.8",
    "requests>=2.31.0",
    "openai>=1.0.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
anki-helpers = "anki_helpers.cli:cli"

[dependency-groups]
dev = [
    "pre-commit>=3.6.0",
    "types-requests>=2.32.0.20250328",
    "mypy>=1.15.0",
    "pytest>=8.3.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/anki_helpers"]

[tool.flake8]
max-line-length = 120  # or whatever length you prefer
```

- ⚠️ hatchling could auto-detect `src/anki_helpers`. The explicit `packages` stops the stray
  `src/__init__.py` from being picked up as a `src` package.
- Python floor 3.14 (D4). Deviates from grand plan design §2 (`>=3.12`).
- ✅ `cli.py` has `version` hardcoded as `"0.1.0"`, so no metadata lookup changes.

CI `.github/workflows/ci.yml` steps after:

| Before | After |
|--------|-------|
| `actions/setup-python@v5` 3.12 | `astral-sh/setup-uv@v6` with `enable-cache: true`; Python from `.python-version` |
| `snok/install-poetry@v1` + `actions/cache` on `.venv` keyed by `poetry.lock` | removed (setup-uv cache) |
| `poetry install --no-interaction` | `uv sync --locked` |
| `poetry run pre-commit run --all-files` | `uv run pre-commit run --all-files` |
| `poetry run pytest` | `uv run pytest` |

## Version drift (D2 + D3)

Lower bounds plus a fresh lock allow new major versions. Current `poetry.lock` pins:

| Package | poetry.lock | Can jump to |
|---------|-------------|-------------|
| `openai` | 1.90.0 | 2.x ⚠️ API may change |
| `click` | 8.1.8 | 8.2+ / 9.x ⚠️ |
| `pre-commit` | 3.8.0 | 4.x |
| `pytest` | 8.3.5 | 9.x |
| `requests`, `python-dotenv`, `mypy`, `types-requests` | 2.32.3, 1.1.0, 1.15.0, 2.32.0.20250328 | minor bumps |

✅ `tests/cli_test.py` replaces `OpenAI` with a local fake (`@patch("anki_helpers.cli.OpenAI", OpenAI)`),
so the tests **do not** catch a change in the real `openai` client API.

> **[HITL-1]** Check: resolved direct-dep versions vs the table above. For an `openai` major jump, confirm
> `client.chat.completions.create(model=..., messages=...)` in `src/anki_helpers/cli.py` still works.
> Why: tests mock OpenAI, so a breaking change ships green. How: `uv tree --depth 1`; if needed run
> `uv run anki-helpers get-examples-for-red-flags-cards --limit 1 /tmp/out` against real Anki + `.env`.
> If it breaks, add an upper bound for that one package only (e.g. `openai>=1.0.0,<2`) and re-lock.

## Test scenarios

**T1 positive: clean install and entry point**
- Given: fresh clone, no `.venv`, uv installed
- Action: `uv sync --locked && uv run anki-helpers --help && uv run anki-helpers version`
- Result: help lists `list-deck`, `list-red-flags`, `get-examples-for-red-flags-cards`; prints `Anki Helpers version 0.1.0`

**T2 positive: checks pass**
- Given: synced env
- Action: `uv run pytest && uv run pre-commit run --all-files`
- Result: all tests pass, all hooks pass

**T3 negative: stale lock is rejected**
- Given: a dep added to `pyproject.toml` without re-locking
- Action: `uv sync --locked`
- Result: non-zero exit, error says lockfile needs update; `.venv` unchanged

**T4 negative: no Poetry left**
- Given: migration done
- Action: `git grep -n -i poetry -- ':!todo.md' ':!docs/tasks/'`
- Result: only `.gitignore` template comments remain

**T5 error handling: Anki not running**
- Given: Anki closed
- Action: `uv run anki-helpers list-deck`
- Result: same error output and exit code as `poetry run anki-helpers list-deck` before migration

## HITL

> **[HITL-1]** Check: resolved versions, real OpenAI call on major jump. Why: tests mock OpenAI. How: `uv tree --depth 1`.

> **[HITL-2]** Check: CI run on the PR is green with the new `ci.yml`. Why: CI cannot be run locally; a wrong
> setup-uv config breaks the main branch gate. ⚠️ Also confirm pre-commit hooks (black 24.2.0, mypy v1.8.0
> mirror) run on 3.14; bump hook `rev`s only if they fail. How: `gh pr checks` on the PR.

## File map

| File | Change | Why |
|------|--------|-----|
| `pyproject.toml` | mod | PEP 621 + hatchling + `dev` group |
| `poetry.lock` | del | replaced |
| `uv.lock` | new | `uv lock` output |
| `.python-version` | new | `3.14` (`uv python pin 3.14`), same Python locally and in CI |
| `.github/workflows/ci.yml` | mod | setup-uv, `uv sync --locked`, `uv run` |
| `README.md` | mod | install/run/test commands → uv |
| `CLAUDE.md` | mod | Setup, Common Commands, Code Quality → uv |
| `.claude/skills/speckit/templates/validation.md` | mod | `poetry …` → `uv …` (needs user approval: sandbox write-protected) |
| `.claude/skills/speckit/templates/tasks.md` | mod | `poetry run` → `uv run` (same) |

## Stages

1. Packaging: `pyproject.toml`, `.python-version`, `poetry.lock`, `uv.lock`. Done when: T1, T2 pass and **[HITL-1]** confirmed.
2. CI: `ci.yml`. Done when: **[HITL-2]** green.
3. Docs + templates: `README.md`, `CLAUDE.md`, speckit templates. Done when: T4 passes.
