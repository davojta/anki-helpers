# anki-helpers
Utils to work with anki app data

## Installation

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

## Running Tests

```bash
# Run all checks (lint + format check + typecheck + test)
just ci

# Individual commands
just test              # pytest with coverage
just test-integration  # integration tests
just test-e2e          # e2e tests (requires RUN_E2E_TESTS=1)
just test-all          # all test tiers
```

## Requirements
- Anki must be running
- AnkiConnect plugin must be installed in Anki
