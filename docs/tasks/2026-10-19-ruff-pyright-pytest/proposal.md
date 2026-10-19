# ruff, pyright, pytest: Proposal

Input: [input.md](input.md) · Stack: [ADR-0001](../../adr/0001-stack.md) · Plan: grand plan S0-03, test half of S0-04

## Summary

Replace black, isort, flake8 and mypy with ruff and pyright (strict on `src/`).
Split tests into `tests/unit/` and `tests/e2e/`, all on pytest. One `make check`
runs everything, locally, in pre-commit and in CI.

## Why

Four overlapping tools today, no type strictness, one test file, no e2e test of
the installed CLI. The grand plan needs one green gate before later stages.

## Current state

- ✅ pre-commit: black 24.2, isort 5.13, flake8 7.0 + docstrings, mypy 1.8 (`.pre-commit-config.yaml`).
- ✅ dev deps: `pre-commit`, `mypy`, `types-requests`, `pytest` (`pyproject.toml`).
- ✅ tests: `tests/cli_test.py` only (2 tests, `CliRunner`, `sys.path` hack, hand-written OpenAI mocks).
- ✅ CI: `.github/workflows/ci.yml` runs `pre-commit run --all-files` + `pytest`.
- ✅ ruff (E,F,W,I,B,UP,D,SIM,RUF,PT): 39 findings, 35 auto-fixable.
- ✅ pyright strict: 32 errors in `src/` (`anki_connect.py` 19, `cli.py` 13), 22 in `tests/`.
  Mostly missing param types and `Any` leaking from `requests` JSON.

## Overview

| Module | Change |
|--------|--------|
| packaging (`pyproject.toml`, `uv.lock`) | Add `ruff`, `pyright`, `pytest-cov` to dev; drop `mypy`; add `[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]` (marker `e2e`) |
| tooling (`.pre-commit-config.yaml`, `Makefile` new) | Hooks: ruff, ruff-format, pyright (local, `uv run`), keep generic + conventional-commit hooks. `make lint / typecheck / test / check` |
| `src/anki_helpers/` | Fix ruff findings; add types to pass pyright strict (no behavior change); new `ANKI_CONNECT_URL` (shell env or `.env`, loaded for every command), `.env.example` |
| `tests/` | `tests/unit/` (CLI via `CliRunner`, `AnkiConnect` with mocked HTTP); `tests/e2e/` (installed `anki-helpers` run as subprocess against a local stub AnkiConnect server); shared `conftest.py`; drop `sys.path` hack |
| CI (`ci.yml`) | Run `make check` |
| docs (`CLAUDE.md`, `README.md`) | New commands, `make check` as the gate |

## Out of scope

- Typer, httpx, pydantic migration (S0-04, S1).
- Full stateful fake AnkiConnect and contract tests (S1).
- Coverage gate (report only for now).
- Real Anki tests and the `real_anki` marker (S1 contract suite). All tests use mocks or the stub.

## Decisions

- [x] D1 e2e scope: Anki commands only (`list-deck`, `list-red-flags`).
  `get-examples-for-red-flags-cards` stays unit-tested.
- [x] D2 e2e stub: small stdlib `http.server` fixture in `tests/e2e/`, replaced by
  the S1 fake later.
- [x] D3 pyright: `strict` on `src/`, `standard` on `tests/`.
- [x] D4 ruff rules: `E,F,W,I,B,UP,D,SIM,RUF,PT`. Wider set adds 6 findings
  (all RUF010, auto-fixable); PT guards the new tests.
