alias t := test

# run all checks (lint + format check + typecheck + test)
[group: 'check']
ci: lint format-check typecheck test

# run tests
[group: 'test']
test:
  poetry run pytest

# run ruff linter
[group: 'check']
lint:
  poetry run ruff check .

# fix ruff lint issues
[group: 'check']
lint-fix:
  poetry run ruff check --fix .

# run ruff formatter
[group: 'check']
format:
  poetry run ruff format .

# check formatting without changes
[group: 'check']
format-check:
  poetry run ruff format --check .

# run pyright type checker
[group: 'check']
typecheck:
  poetry run pyright
