# anki-helpers
Utils to work with anki app data

## Installation

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.14 (from `.python-version`) if needed.

```bash
uv sync
```

## Usage

### List all decks
```bash
uv run anki-helpers list-deck
```

### List all words with red flags
```bash
uv run anki-helpers list-red-flags [--limit N]
```

This command will list notes in Anki that have been marked with a red flag (using the 'marked' tag in Anki). The notes are sorted by their due date in descending order, making it easy to see which cards need to be reviewed first. By default, only the top 5 cards are displayed, but you can change this using the `--limit` parameter.

### Generate example sentences for red flag cards
```bash
uv run anki-helpers get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR
```

This command will:
1. Query all cards with red flags in Anki
2. Create a markdown file `input-words.md` in the specified output directory with the content of these cards
3. Call the OpenAI API (GPT-4o) to generate example sentences for these words
4. Output the response to the console and save it to `results.md` in the output directory

By default, all red flag cards are processed, but you can limit the number of words using the `--limit` parameter.

**Requirements:**
- Python packages: `openai`, `python-dotenv`
- A `.env` file in the project root with your OpenAI API key: `API_KEY = "your-api-key"`

### Fake AnkiConnect (no Anki needed)

A stateful AnkiConnect v6 emulator for testing queries and commands without a running Anki.

```bash
# Try a search query against the bundled sample collection (offline, no server)
uv run anki-helpers mock query "flag:1 prop:due<0"
uv run anki-helpers mock query --cards "deck:German -is:new (tag:noun or tag:verb)"

# Serve it over HTTP and point any AnkiConnect client at it
uv run anki-helpers mock serve --port 8765 [--seed my.json | --empty] [--dump-on-exit out.json]
ANKI_CONNECT_URL=http://127.0.0.1:8765 uv run anki-helpers list-red-flags
curl -s localhost:8765 -d '{"action":"findNotes","version":6,"params":{"query":"tag:noun"}}'
```

- Sample collection: `src/anki_helpers/fake_anki/fixtures/basic.json` (also the seed file format).
- Debug endpoints: `GET /_state` (dump as seed), `GET /_log` (requests received),
  `POST /_reset` (back to startup seed), `POST /_seed` (load a seed),
  `POST /_faults` (`{"action": "findNotes", "error": "collection is not available", "times": 1, "latency_ms": 0}`; `[]` clears).
- Search subset: `and`/`or`/`-`/parentheses/quotes, bare text and `field:value` with `*` `_` wildcards,
  `deck:` (incl. subdecks), `tag:` (incl. child tags, `tag:none`), `note:`, `card:`, `nid:`, `cid:`, `flag:`,
  `is:new|learn|review|due|suspended|buried`, `prop:due|ivl|reps|lapses|ease` with `= != < <= > >=`, `edited:N`.
  Anything else (e.g. `added:`, `rated:`) is rejected with an error rather than silently matching.
- In the fake, a review card's `due` in the seed is days relative to today (`-3` = 3 days overdue).

## Configuration

Copy `.env.example` to `.env` and fill in:

- `API_KEY` — OpenAI API key (for `get-examples-for-red-flags-cards`)
- `ANKI_CONNECT_URL` — AnkiConnect endpoint (default `http://localhost:8765`)

Shell environment variables override `.env`.

## Development

```bash
make check        # lint + typecheck + tests (the full gate)
make lint         # ruff check + ruff format --check
make typecheck    # pyright
make test         # pytest with coverage
make test-unit    # unit tests only
make test-e2e     # end-to-end tests only
make fmt          # auto-fix lint and formatting
```

## Requirements
- Anki must be running
- AnkiConnect plugin must be installed in Anki
