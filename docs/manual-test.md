# Anki Helpers CLI — Manual Test Document

*2026-03-31T18:43:25Z by Showboat 0.6.1*
<!-- showboat-id: df673ca5-423c-45a0-8542-f7f3f31e487a -->

This document serves as a manual test suite for the Anki Helpers CLI. Each section exercises a command against a live Anki instance (AnkiConnect on localhost:8765). Re-run with `showboat verify` to check reproducibility.

```bash
uv run anki-helpers --help
```

```output
Usage: anki-helpers [OPTIONS] COMMAND [ARGS]...

  Anki Helpers - A CLI tool to help with Anki flashcards.

Options:
  --help  Show this message and exit.

Commands:
  generate-examples-for-word      Generate example sentences for words...
  get-examples-for-red-flags-cards
                                  Generate example sentences for red...
  hello-world                     Print a hello world message.
  list-deck                       List all available Anki decks.
  list-red-flags                  List all words with red flags in...
  version                         Show the version of Anki Helpers.
```

## list-deck — List all decks

```bash
uv run anki-helpers list-deck
```

```output
Available decks:
  • Basic Vocabulary Eng-Fin
  • Custom Study Session
  • Default
  • Finnish Grammar
  • Jokapäiväistä sanastoa
  • Opettajan sanastoa
  • Verbit
  • [W/ audio] Finnish - English Core 900 (Spoken Language)
```

## version — Show version

```bash
uv run anki-helpers version
```

```output
Anki Helpers version 0.1.0
```

## hello-world — Smoke test

```bash
uv run anki-helpers hello-world
```

```output
Hello World!
```

## list-red-flags — List red-flagged cards

```bash
uv run anki-helpers list-red-flags --limit 5
```

```output
Cards with red flags (sorted by due date, showing top 5):
  • ero
    Due: 2026-03-29

  • esiin (esi - pre-, fore-) | Totuus tuli esiin tutkimuksessa.
    Due: 2026-03-29

  • kohta (*kokta-> kopta (place)) | pian, lähihetkinä | se olis kohta tulos
    Due: 2026-03-29
    Tags: leech

  • käytännöllinen | Pyörä on käytännöllinen
    Due: 2026-03-29

  • näyttää | Tuo maalaus näyttää hyvältä.
    Due: 2026-03-29

```

## generate-examples-for-word — Generate examples from word list

```bash
uv run anki-helpers generate-examples-for-word --help
```

```output
Usage: anki-helpers generate-examples-for-word [OPTIONS] WORDS_FILE

  Generate example sentences for words from a file.

  This command: 1. Reads words from the specified file 2. Calls OpenAI API to
  generate examples in markdown table format 3. Outputs the response to
  console and saves to examples-table.md

  Args:     words_file: Path to markdown file containing words in Finnish
  topics: Comma-separated topics for example sentences

Options:
  --topics TEXT  Comma-separated list of topics for example sentences
  --help         Show this message and exit.
```

## get-examples-for-red-flags-cards — Generate examples for red-flagged cards

```bash
uv run anki-helpers get-examples-for-red-flags-cards --help
```

```output
Usage: anki-helpers get-examples-for-red-flags-cards [OPTIONS] OUTPUT_DIR

  Generate example sentences for red flag cards.

  This command: 1. Queries cards with red flags 2. Creates a markdown file
  with the content of these cards 3. Calls OpenAI API to generate example
  sentences 4. Outputs the response to console and file

  Args:     output_dir: Directory where output files will be saved     limit:
  Maximum number of words to process (default: all words)

Options:
  --limit INTEGER  Limit the number of words to process
  --help           Show this message and exit.
```
