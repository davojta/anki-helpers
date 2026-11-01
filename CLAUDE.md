# anki-helpers

Python CLI tool for working with Anki flashcard data via the AnkiConnect plugin.

## Setup

```bash
uv sync
```

## Common Commands

```bash
# Full gate: lint + typecheck + tests (run before commit/PR)
make check

# Individual steps
make lint         # ruff check + ruff format --check
make typecheck    # pyright
make test         # pytest with coverage
make test-unit    # pytest -m "not e2e"
make test-e2e     # pytest -m e2e
make fmt          # ruff check --fix + ruff format

# Run the CLI
uv run anki-helpers --help
uv run anki-helpers list-deck
uv run anki-helpers list-red-flags [--limit N]
uv run anki-helpers query-anki list --filter flag=red:due_date=<10d [--sort due|interval] [--limit N]
uv run anki-helpers generate-examples-for-word WORDS_FILE [--topics "A,B"] [--output FILE]
uv run anki-helpers get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR

# Fake AnkiConnect (no Anki needed)
uv run anki-helpers mock query "flag:1 prop:due<0" [--cards] [--seed F | --empty]
uv run anki-helpers mock serve --port 8765 [--seed F | --empty] [--dump-on-exit OUT]
```

## Architecture

- `src/anki_helpers/cli.py` — CLI entry point; all Click commands live here
- `src/anki_helpers/anki_connect.py` — AnkiConnect HTTP API wrapper
- `src/anki_helpers/prompts/` — Prompt templates for OpenAI calls
- `docs/anki-connect-api.md` — AnkiConnect v6 reference: schemas, search syntax, `due` conversion (verified live)
- `src/anki_helpers/fake_anki/` — fake AnkiConnect v6: `state.py` (collection, seed load/dump), `search.py` (Anki query subset), `actions.py` (`FakeAnki` action handlers), `server.py` (HTTP + `/_state` `/_log` `/_reset` `/_seed` `/_faults`), `fixtures/basic.json` (sample seed)
- `tests/unit/` — Click `CliRunner` tests and client tests; AnkiConnect and OpenAI HTTP are mocked
- `tests/e2e/` — runs the installed CLI against a stdlib stub AnkiConnect server and against the fake (`fake_anki.running()`)
- `tests/conftest.py` — shared fixtures (isolated env, `.env` handling)

## Code Quality

Local pre-commit hooks run on commit (via `uv run`, versions from `uv.lock`):

- **ruff check** — lint (`--fix`)
- **ruff format** — formatting
- **pyright** — type checking; strict on `src/`, standard on `tests/`
- **pre-commit-hooks** — whitespace, EOF, YAML/TOML/JSON syntax, debug statements, etc.
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

Copy the template and fill in values:

```bash
cp .env.example .env
```

- `API_KEY` — OpenAI API key; required by `get-examples-for-red-flags-cards` and `generate-examples-for-word`
- `ANKI_CONNECT_URL` — AnkiConnect endpoint; default `http://localhost:8765`

Shell environment variables take precedence over `.env`. `.env` is git-ignored.

## Requirements

- Anki must be running with the AnkiConnect plugin installed for commands that talk to Anki.
- OpenAI commands require a valid `API_KEY` (in `.env` or the shell environment).
