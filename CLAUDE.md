# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python CLI tool for interacting with Anki flashcards through the AnkiConnect plugin. The project uses uv for dependency management and Click for the CLI interface.

## Development Commands

### Setup and Installation
```bash
uv sync
```

### Running Commands
```bash
# Run the CLI tool
uv run anki-helpers --help

# List all available Anki decks
uv run anki-helpers list-deck

# List red-flagged cards (cards marked with flag:1)
uv run anki-helpers list-red-flags [--limit N]

# Generate example sentences for red-flagged cards using OpenAI
uv run anki-helpers get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR

# Generate examples for specific words from a file
uv run anki-helpers generate-examples-for-word WORDS_FILE [--topics "topic1,topic2,topic3"]
```

## Code Validation

Run these before considering any task complete:

```bash
# Run all checks (lint + format check + typecheck + test)
just ci

# Individual commands
just lint          # ruff linter
just lint-fix      # ruff auto-fix
just format        # ruff formatter
just format-check  # check formatting without changes
just typecheck     # pyright type checker
just test          # pytest with coverage
just test-integration # integration tests
just test-e2e      # e2e tests (requires RUN_E2E_TESTS=1)
just test-all      # all test tiers
```

## Architecture

### Core Components

- **CLI Interface** (`src/anki_helpers/cli.py`): Main CLI commands using Click framework
- **AnkiConnect Client** (`src/anki_helpers/anki_connect.py`): API client for communicating with Anki via AnkiConnect plugin
- **Prompts** (`src/anki_helpers/prompts/`): Templates for AI-generated content

### Key Features

1. **Deck Management**: List all available Anki decks
2. **Red Flag Tracking**: Find and display cards marked with red flags (flag:1 in Anki)
3. **AI Integration**: Generate example sentences for difficult words using OpenAI's GPT-4o
4. **Word Examples**: Generate structured examples for specific words from input files

### AnkiConnect Integration

The project requires:
- Anki application running
- AnkiConnect plugin installed in Anki
- AnkiConnect listens on `http://localhost:8765` by default

### Environment Configuration

Create a `.env` file in the project root for OpenAI integration:
```
API_KEY=your-openai-api-key
```

### Data Flow for Red Flag Cards

1. Query Anki for cards with `flag:1`
2. Retrieve card content, due dates, and intervals
3. Sort by due date for prioritization
4. Generate AI prompts for difficult words
5. Save results to markdown files in specified output directory

### Output Structure

The `get-examples-for-red-flags-cards` command creates:
- `input-words.md`: List of words from red-flagged cards
- `results.md`: AI-generated example sentences
- `debug-prompt.txt`: Full prompt sent to OpenAI for debugging

### Testing Strategy

Three-tier testing:
- **Unit tests** (`tests/`): Individual functions and classes, mocked external services
- **Integration tests** (`integration-tests/`): CLI commands via subprocess
- **E2E tests** (`e2e-tests/`): Full CLI workflows, guarded by `RUN_E2E_TESTS=1` env var

Fixtures available in `tests/conftest.py`: `mock_anki_connect`, `mock_openai`
