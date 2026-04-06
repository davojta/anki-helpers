## ADDED Requirements

### Requirement: Sync command with two modes
The system SHALL provide a `sync` CLI command that synchronizes Anki data into the local SQLite database. The sync mode is determined automatically based on sync history:

- **Initial sync** (no previous sync_log entry): Full load of ALL notes and cards from Anki.
- **Incremental sync** (previous sync exists): Fetch only notes modified since the last sync.

The `due_query` field SHALL be computed from the raw `due` value from `cardsInfo`, converted to relative days based on queue type (see design decision #4). The `flag` field SHALL store the value from `cardsInfo.flags` (0-7). The `queue` field SHALL store the value from `cardsInfo.queue`.

#### Scenario: Initial sync (no previous sync)
- **WHEN** user runs `anki-helpers sync` and no previous sync exists in sync_log
- **THEN** the system calls `notesInfo(query="")` to get all note data (fields, tags, mod, cards) — single call replaces `findNotes` + `notesInfo`
- **THEN** the system collects all card IDs from `notesInfo.cards` fields
- **THEN** the system calls `cardsInfo(cards=all_card_ids)` to get card-level data (deck, due, interval, flags, queue)
- **THEN** the system determines `days_elapsed` by calling `findCards("prop:due=0")` and reading the raw `due` value of a returned card
- **THEN** the system converts raw `due` to `due_query` (relative days) based on queue type
- **THEN** the system stores all data via `replace_all(notes)`
- **THEN** a sync log entry is created with synced_at, total_cards, deck_count, new_cards, updated_cards
- **THEN** the command prints: timestamp, total cards, decks, new cards, updated cards

#### Scenario: Incremental sync (previous sync exists)
- **WHEN** user runs `anki-helpers sync` and a previous sync exists in sync_log
- **THEN** the system reads `synced_at_epoch` from the most recent sync_log row
- **THEN** the system calculates N = max(1, ceil((now - synced_at_epoch) / 86400) + 1) (safety margin in days)
- **THEN** the system calls `findNotes("edited:N")` to get recently modified note IDs (note: `prop:mod` does not exist as a search operator)
- **THEN** the system calls `notesInfo(notes=note_ids)` for those note IDs
- **THEN** the system filters notes to only those with `mod > synced_at_epoch` (client-side precision filter, since `edited:N` uses scheduler day boundary, not exact epoch)
- **THEN** for filtered notes, the system collects card IDs from `notesInfo.cards` fields and calls `cardsInfo`
- **THEN** the system determines `days_elapsed` and converts `due_query`
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

### Requirement: query-local command
The system SHALL provide a `query-local SQL` command that executes an arbitrary SQL query against `.anki-cache.db` and prints results in table format.

#### Scenario: Valid SELECT query
- **WHEN** user runs `anki-helpers query-local "SELECT COUNT(*) FROM notes;"`
- **THEN** the system executes the SQL against `.anki-cache.db` and prints results as a table

#### Scenario: Query with no database
- **WHEN** user runs `anki-helpers query-local "SELECT COUNT(*) FROM notes;"` and `.anki-cache.db` does not exist
- **THEN** the system prints an error: "No local database found. Run `sync` first."

#### Scenario: Invalid SQL
- **WHEN** user runs `anki-helpers query-local "INVALID SQL"`
- **THEN** the system prints the SQLite error message

#### Scenario: Non-SELECT statement
- **WHEN** user runs `anki-helpers query-local "DELETE FROM notes;"`
- **THEN** the system prints an error: "Only SELECT queries are allowed."

### Requirement: query-anki list command
The system SHALL provide a `query-anki list` subcommand with `--filter` and `--sort` options that queries Anki directly via AnkiConnect (no local cache required).

**Filter syntax**: `--filter key=value` with `:` separator for multiple filters. Multiple filters are combined with AND logic.

Supported filter keys:
| Key | Value format | Anki search translation |
|-----|-------------|------------------------|
| `flag` | `none`, `red`, `orange`, `green`, `blue`, `pink`, `turquoise`, `purple` | `flag:0` through `flag:7` |
| `due_date` | `<Nd` or `>Nd` (N = number of days) | `prop:due<N` or `prop:due>N` |

**Sort options**: `--sort FIELD` where FIELD is `due` (default) or `interval`.

Output: table with columns card_id, note_id, deck, due, flag, fields summary, tags.

#### Scenario: Filter by red flag, sort by due
- **WHEN** user runs `anki-helpers query-anki list --filter flag=red --sort due`
- **THEN** the system translates to Anki search `flag:1`
- **THEN** results are sorted by due ascending and printed as a table

#### Scenario: Filter by due date
- **WHEN** user runs `anki-helpers query-anki list --filter due_date=<10d --sort due`
- **THEN** the system translates to Anki search `prop:due<10`
- **THEN** results are sorted by due ascending and printed as a table

#### Scenario: Multiple filters combined
- **WHEN** user runs `anki-helpers query-anki list --filter flag=red:due_date=<10d --sort due`
- **THEN** the system translates to Anki search `flag:1 prop:due<10`
- **THEN** results are sorted by due ascending and printed as a table

#### Scenario: No matching cards
- **WHEN** user runs `anki-helpers query-anki list --filter flag=blue` and no blue-flagged cards exist
- **THEN** the system prints "No cards found."

#### Scenario: Unknown filter key
- **WHEN** user runs `anki-helpers query-anki list --filter unknown=value`
- **THEN** the system prints an error: "Unknown filter: unknown. Supported filters: flag, due_date"

#### Scenario: Invalid filter value
- **WHEN** user runs `anki-helpers query-anki list --filter flag=yellow`
- **THEN** the system prints an error: "Invalid flag value: yellow. Supported: none, red, orange, green, blue, pink, turquoise, purple"

#### Scenario: Anki not running
- **WHEN** user runs `anki-helpers query-anki list` and AnkiConnect is unreachable
- **THEN** the command exits with a clear error message indicating Anki is not available

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
