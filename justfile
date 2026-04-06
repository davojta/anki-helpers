alias t := test

# run all checks (lint + format check + typecheck + test)
[group: 'check']
ci: lint format-check typecheck test

# run unit tests with coverage
[group: 'test']
test:
  uv run pytest tests/ -v --cov=src --cov-report=term-missing

# run integration tests
[group: 'test']
test-integration:
  uv run pytest integration-tests/ -v

# run e2e tests
[group: 'test']
test-e2e:
  uv run pytest e2e-tests/ -v

# run all tests (unit + integration + e2e)
[group: 'test']
test-all: test test-integration test-e2e

# run ruff linter
[group: 'check']
lint:
  uv run ruff check src/ tests/ integration-tests/ e2e-tests/

# fix ruff lint issues
[group: 'check']
lint-fix:
  uv run ruff check --fix src/ tests/ integration-tests/ e2e-tests/

# run ruff formatter
[group: 'check']
format:
  uv run ruff format src/ tests/ integration-tests/ e2e-tests/

# check formatting without changes
[group: 'check']
format-check:
  uv run ruff format --check src/ tests/ integration-tests/ e2e-tests/

# run pyright type checker
[group: 'check']
typecheck:
  uv run pyright
