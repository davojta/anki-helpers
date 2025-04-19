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

## Requirements
- Anki must be running
- AnkiConnect plugin must be installed in Anki
