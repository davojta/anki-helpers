# anki-helpers
Utils to work with anki app data

## Installation

```bash
poetry install
```

## Usage

### List all decks
```bash
poetry run anki-helpers list-deck
```

### List all words with red flags
```bash
poetry run anki-helpers list-red-flags [--limit N]
```

This command will list notes in Anki that have been marked with a red flag (using the 'marked' tag in Anki). The notes are sorted by their due date in descending order, making it easy to see which cards need to be reviewed first. By default, only the top 5 cards are displayed, but you can change this using the `--limit` parameter.

### Generate example sentences for red flag cards
```bash
poetry run anki-helpers get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR
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

To run the tests for this project, you can use Python's built-in unittest framework through Poetry:

```bash
# Run all tests
poetry run python -m unittest discover tests

# Run a specific test file
poetry run python -m unittest tests/cli_test.py

# Run a specific test function
poetry run python -m unittest tests.cli_test.test_version
```

Alternatively, you can install pytest and use it to run the tests:

```bash
# Install pytest
poetry add --dev pytest

# Run all tests
poetry run pytest

# Run a specific test file
poetry run pytest tests/cli_test.py

# Run a specific test function
poetry run pytest tests/cli_test.py::test_version
```

## Requirements
- Anki must be running
- AnkiConnect plugin must be installed in Anki
