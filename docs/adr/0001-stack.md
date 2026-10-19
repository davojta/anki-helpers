# ADR-0001: Project stack

- Status: accepted
- Date: 2026-10-19
- Resolves: open decision D1 (mypy vs pyright) of
  [the grand plan](../tasks/2026-10-19-grand-plan/proposal.md)
- Source: grand plan [design.md §2](../tasks/2026-10-19-grand-plan/design.md)

## Context

anki-helpers started as a Poetry + unittest Click CLI with black, isort,
flake8 and mypy in pre-commit. The grand plan rebuilds it as a typed,
agent-friendly project: small issues implemented by Claude Code, each checked
by a single `make check` locally, in pre-commit and in CI. That needs one
tool per concern and a stack every later stage (fake AnkiConnect, Markdown
vault, sync, MCP server, LLM generation, web UI) can share.

## Decision

| Concern | Choice |
|---|---|
| Python | 3.14 only (CI), `requires-python >=3.14` |
| Env/packaging | **uv** + `pyproject.toml` (PEP 621), `uv.lock`, hatchling backend |
| Lint/format | **ruff** (`check` + `format`), replacing flake8, black and isort |
| Types | **pyright**, strict on `src/` (see below) |
| Tests | **pytest**, pytest-cov, `httpx.MockTransport` fixtures, hypothesis for parser round-trips; unit and e2e tests never touch a real Anki or the network |
| CLI | **Typer** (Click underneath) + Rich |
| HTTP | **httpx** (sync + async), replacing requests |
| Models | **pydantic v2** at boundaries: front matter, AnkiConnect payloads, LLM output |
| Markdown | `python-frontmatter` / `ruamel.yaml`, `markdown-it-py` (MD→HTML), `markdownify` (HTML→MD) |
| Hooks | pre-commit: ruff, ruff-format, pyright, end-of-file/trailing-ws, conventional commits |
| Task runner | `Makefile`; `make check` = ruff check + ruff format --check + pyright + pytest |
| Scaffolding | copier, if a template is used |

uv is already in place (task `2026-10-19-uv-migration`). The rest lands
through Stage 0 of the grand plan.

### Type checker: pyright over mypy

Use **pyright** as the only type checker.

- Install it as a dev dependency (`pyright` from PyPI), so `uv run pyright`
  works the same locally, in pre-commit and in CI.
- Configure it under `[tool.pyright]` in `pyproject.toml`:
  `typeCheckingMode = "standard"` globally, `strict = ["src"]` for `src/`.
- Remove mypy from the dev dependencies and from `.pre-commit-config.yaml`.

Why:

- **Editor parity:** pyright is the engine behind Pylance, so editor errors
  match CI errors.
- **Speed:** fast enough for every save and every commit.
- **No plugins needed:** pydantic v2 uses `dataclass_transform`, which
  pyright supports natively; mypy needs the pydantic plugin.
- **Stricter inference:** pyright infers types for unannotated code and
  narrows more aggressively, catching more mistakes in agent-written code.

Alternatives: `mypy --strict` (the plan's default) was rejected for slower
runs, plugin reliance and editor mismatch. Running both was rejected as
duplicate, sometimes conflicting noise.

## Consequences

- One command, `make check`, gates every PR; CLAUDE.md and CI call it.
- Pyright needs Node.js; the PyPI wrapper downloads it on first run. If that
  hurts CI or fresh clones, switch to `basedpyright`, a self-contained wheel.
- mypy idioms (`# type: ignore[code]`, plugins) don't carry over; use
  `# pyright: ignore[rule]`.
- The legacy CLI moves from Click to Typer and from requests to httpx; the
  `list-deck`, `list-red-flags` and `get-examples-for-red-flags-cards`
  signatures are preserved.
