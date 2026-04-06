## ADDED Requirements

### Requirement: Sync command with two modes
The system SHALL provide a `sync` CLI command that synchronizes Anki data into the local SQLite database. The sync mode is determined automatically based on sync history:

- **Initial sync** (no previous sync_log entry): Full load of ALL notes and cards from Anki.
- **Incremental sync** (previous sync exists): Fetch only notes modified since the last sync.

The `due_query` field SHALL be set to the `due` value from `cardsInfo`.

#### Scenario: Initial sync (no previous sync)
- **WHEN** user runs `anki-helpers sync` and no previous sync exists in sync_log
- **THEN** the system calls `findNotes("")` to get all note IDs
- **THEN** the system calls `notesInfo` with all note IDs
- **THEN** the system calls `findCards("")` to get all card IDs
- **THEN** the system calls `cardsInfo` with all card IDs
- **THEN** the system stores all data via `replace_all(notes)`
- **THEN** a sync log entry is created with synced_at, total_cards, deck_count, new_cards, updated_cards
- **THEN** the command prints: timestamp, total cards, decks, new cards, updated cards

#### Scenario: Incremental sync (previous sync exists)
- **WHEN** user runs `anki-helpers sync` and a previous sync exists in sync_log
- **THEN** the system reads `synced_at_epoch` from the most recent sync_log row
- **THEN** the system calculates N = ceil((now - synced_at_epoch) / 86400) + 1 (safety margin in days)
- **THEN** the system calls `findNotes("prop:mod:N")` to get recently modified note IDs
- **THEN** the system calls `notesInfo` for those note IDs
- **THEN** the system filters notes to only those with `mod > synced_at_epoch` (client-side precision filter)
- **THEN** for filtered notes, the system gets card IDs and calls `cardsInfo`
- **THEN** the system stores data via `upsert_notes(notes)`
- **THEN** a sync log entry is created
- **THEN** the command prints: timestamp, cards processed, new cards, updated cards

#### Scenario: Incremental sync with no changes
- **WHEN** user runs `anki-helpers sync` and no notes have been modified since last sync
- **THEN** the command prints "No changes since last sync" with the last sync timestamp
- **THEN** no sync log entry is created

#### Scenario: Anki not running
- **WHEN** user runs `anki-helpers sync` and AnkiConnect is unreachable
- **THEN** the command exits with a clear error message indicating Anki is not available
- **THEN** no changes are made to the SQLite database

#### Scenario: Partial fetch failure
- **WHEN** AnkiConnect responds to initial API calls but fails during data retrieval
- **THEN** the command exits with an error message indicating which API call failed
- **THEN** no changes are made to the SQLite database (atomicity preserved)

### Requirement: Local flag on list-red-flags
The `list-red-flags` command SHALL accept a `--local` flag. When set, the command SHALL read card data from the SQLite cache instead of making live AnkiConnect calls.

#### Scenario: List red flags from cache
- **WHEN** user runs `anki-helpers list-red-flags --local`
- **THEN** the system queries the SQLite database for red-flagged notes via `get_cards_by_flag(1)`
- **THEN** results are displayed in the same format and sort order (by due_query ascending) as the live version

#### Scenario: Local flag without prior sync
- **WHEN** user runs `anki-helpers list-red-flags --local` and no sync has been performed
- **THEN** the system displays a warning that no cached data is available and suggests running `sync` first

### Requirement: Local flag on get-examples-for-red-flags-cards
The `get-examples-for-red-flags-cards` command SHALL accept a `--local` flag. When set, the command SHALL read card data from the SQLite cache.

#### Scenario: Generate examples from cache
- **WHEN** user runs `anki-helpers get-examples-for-red-flags-cards --local OUTPUT_DIR`
- **THEN** the system reads red-flagged notes from SQLite and generates examples using OpenAI

### Requirement: Stale data warning
The system SHALL warn the user when cached data is older than 24 hours.

#### Scenario: Data older than 24 hours
- **WHEN** a `--local` command is run and the last sync was more than 24 hours ago
- **THEN** the system prints a warning suggesting to run `sync` to update the cache
