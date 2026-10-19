# anki-helpers

Python CLI tool for working with Anki flashcard data via the AnkiConnect plugin.

## Setup

```bash
uv sync
```

## Common Commands

```bash
# Run all tests
uv run pytest

# Run the CLI
uv run anki-helpers --help
uv run anki-helpers list-deck
uv run anki-helpers list-red-flags [--limit N]
uv run anki-helpers get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR
```

## Architecture

- `src/anki_helpers/cli.py` — CLI entry point; all Click commands live here
- `src/anki_helpers/anki_connect.py` — AnkiConnect HTTP API wrapper
- `src/anki_helpers/prompts/` — Prompt templates for OpenAI calls
- `tests/cli_test.py` — Tests using Click's `CliRunner`; AnkiConnect and OpenAI are mocked

## Code Quality

Pre-commit hooks run automatically on commit:

- **black** — code formatting
- **isort** — import sorting (black profile)
- **flake8** — linting (max line length 120, docstrings required)
- **mypy** — static type checking
- **conventional-pre-commit** — enforces conventional commit messages

Install hooks after cloning:

```bash
uv run pre-commit install --hook-type commit-msg
```

Run hooks manually:

```bash
uv run pre-commit run --all-files
```

## Environment

`get-examples-for-red-flags-cards` requires an OpenAI API key. Create a `.env` file in the project root:

```
API_KEY="your-openai-api-key"
```

## Requirements

- Anki must be running with the AnkiConnect plugin installed for commands that talk to Anki.
- OpenAI commands require a valid `API_KEY` in `.env`.
