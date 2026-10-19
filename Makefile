.PHONY: lint typecheck test test-unit test-e2e check fmt

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest --cov=anki_helpers --cov-report=term-missing

test-unit:
	uv run pytest -m "not e2e"

test-e2e:
	uv run pytest -m e2e

check: lint typecheck test

fmt:
	uv run ruff check --fix .
	uv run ruff format .
