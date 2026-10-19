# Migrate from Poetry to uv: Proposal

Input: [input.md](input.md) · Parent: [grand plan](../2026-10-19-grand-plan/proposal.md) (S0-02)

## Summary

Replace Poetry with uv for venv, lock, and run. Move `pyproject.toml` to PEP 621 metadata
with the hatchling build backend. Swap `poetry.lock` for `uv.lock`. No code or behavior changes.

## Why

The grand plan's stack (design §2) uses uv + hatchling. Every later stage assumes
`uv sync` / `uv run`. One tool for venv, lock, and run; faster CI installs.

## Overview

| Module | Change |
|--------|--------|
| packaging | `pyproject.toml`: `[tool.poetry]` → `[project]` + `[project.scripts]` + `[dependency-groups] dev`; build backend `poetry-core` → `hatchling`. ✅ current file has no `packages` key; src layout `src/anki_helpers` |
| packaging | delete `poetry.lock`; add `uv.lock` (`uv lock`). ✅ `.gitignore` does not ignore `uv.lock` |
| packaging | add `.python-version` = `3.14` |
| CI | `.github/workflows/ci.yml`: `setup-python` 3.12 + `snok/install-poetry` + `.venv` cache → `astral-sh/setup-uv` (built-in cache, Python 3.14); `uv sync --locked`; `uv run pre-commit …`, `uv run pytest` |
| docs | `README.md`, `CLAUDE.md`: `poetry install` → `uv sync`, `poetry run` → `uv run`, `poetry add --dev` → `uv add --dev` |
| `.claude/skills` | `speckit/templates/validation.md`, `speckit/templates/tasks.md`: `poetry run` → `uv run` |

Unchanged: `.pre-commit-config.yaml` (hooks don't call Poetry ✅), `src/**`, `tests/**`,
`todo.md` (history).

## Out of scope

- ruff, mypy --strict, Makefile (S0-03).
- unittest→pytest cleanup in README, Click→Typer (S0-04).
- Removing the stray `src/__init__.py` or the unused `[tool.flake8]` section.
- Dependency upgrades beyond what a fresh `uv lock` resolves.

## Decisions

- [x] D1 Dev deps in `[dependency-groups] dev` (PEP 735, synced by default).
- [x] D2 Lower bounds only (`click>=8.1.8`); `uv.lock` does the pinning.
- [x] D3 Fresh `uv lock`; green tests are the check.
- [x] D4 `requires-python = ">=3.14"`, pinned via `.python-version`; CI on 3.14. Overrides grand plan §2 (`>=3.12`).
