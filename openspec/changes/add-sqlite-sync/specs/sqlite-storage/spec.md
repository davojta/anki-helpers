## ADDED Requirements

### Requirement: SQLite database initialization
The system SHALL create a SQLite database at `.anki-cache.db` with `notes` and `sync_log` tables when first accessed.

The `notes` table SHALL store: `card_id` (INTEGER PK), `note_id` (INTEGER), `deck_name` (TEXT), `fields` (TEXT, JSON), `tags` (TEXT, JSON), `due` (INTEGER), `interval` (INTEGER), `flag` (INTEGER), `due_query` (INTEGER), `modified` (INTEGER — Anki note modification epoch).

The `sync_log` table SHALL store: `id` (INTEGER PK AUTOINCREMENT), `synced_at` (TEXT, ISO timestamp), `synced_at_epoch` (INTEGER), `total_cards` (INTEGER), `deck_count` (INTEGER), `new_cards` (INTEGER), `updated_cards` (INTEGER).

#### Scenario: First access creates database
- **WHEN** SQLiteStorage is initialized and the database file does not exist
- **THEN** the system creates `.anki-cache.db` with `notes` and `sync_log` tables and correct schema

#### Scenario: Subsequent access reuses database
- **WHEN** SQLiteStorage is initialized and the database file already exists
- **THEN** the system connects to the existing database without recreating tables

### Requirement: Full replacement for initial load
The system SHALL support bulk replacement of all cached notes within a single database transaction. This method SHALL only be used for the initial sync when the database is empty.

The method signature SHALL be `replace_all(notes) -> SyncLogEntry`. The entire operation (delete + insert) MUST be atomic: either all new data is committed or no changes are made.

#### Scenario: Initial load replaces all cached notes
- **WHEN** `replace_all(notes)` is called with new data
- **THEN** all previous rows in `notes` are removed and new rows are inserted atomically
- **THEN** a sync log entry is recorded with `new_cards=len(notes)`, `updated_cards=0`

#### Scenario: Empty data clears cache
- **WHEN** `replace_all([])` is called
- **THEN** all rows are removed from `notes`
- **THEN** a sync log entry is recorded with `total_cards=0`, `new_cards=0`, `updated_cards=0`

#### Scenario: Failed initial load preserves existing data
- **WHEN** `replace_all(notes)` is called and an error occurs during insert
- **THEN** the transaction is rolled back and existing data remains unchanged
- **THEN** no sync log entry is created

### Requirement: Incremental upsert for subsequent syncs
The system SHALL support incremental updates via `upsert_notes(notes) -> (new_count, updated_count)`. For each note, if its `card_id` already exists in the `notes` table, the row is updated. If not, a new row is inserted. The method MUST be atomic (all upserts succeed or none do).

#### Scenario: Mix of new and existing cards
- **WHEN** `upsert_notes(notes)` is called with 5 notes, of which 3 have existing card_ids and 2 are new
- **THEN** 3 existing rows are updated and 2 new rows are inserted atomically
- **THEN** the method returns `(new_count=2, updated_count=3)`

#### Scenario: All cards are new
- **WHEN** `upsert_notes(notes)` is called with notes whose card_ids are not in the database
- **THEN** all notes are inserted
- **THEN** the method returns `(new_count=len(notes), updated_count=0)`

#### Scenario: All cards already exist
- **WHEN** `upsert_notes(notes)` is called with notes whose card_ids all exist in the database
- **THEN** all existing rows are updated
- **THEN** the method returns `(new_count=0, updated_count=len(notes))`

#### Scenario: Empty upsert is a no-op
- **WHEN** `upsert_notes([])` is called
- **THEN** no changes are made to the database
- **THEN** the method returns `(new_count=0, updated_count=0)`

### Requirement: Add sync log entry
The system SHALL provide an `add_sync_log(total_cards, deck_count, new_cards, updated_cards)` method that inserts a row into `sync_log` with the current UTC timestamp as `synced_at` and the current epoch as `synced_at_epoch`.

#### Scenario: Record sync log
- **WHEN** `add_sync_log(150, 5, 12, 8)` is called
- **THEN** a row is inserted with `synced_at=<current UTC ISO timestamp>`, `synced_at_epoch=<current epoch>`, `total_cards=150`, `deck_count=5`, `new_cards=12`, `updated_cards=8`

### Requirement: Query cards with red flag
The system SHALL support querying notes filtered by flag value, sorted by `due_query` ascending.

#### Scenario: Query red-flagged cards
- **WHEN** `get_cards_by_flag(1)` is called
- **THEN** the system returns all notes with flag=1, sorted by `due_query` ascending

#### Scenario: No matching cards
- **WHEN** `get_cards_by_flag(1)` is called and no notes have flag=1
- **THEN** the system returns an empty list

### Requirement: List all decks
The system SHALL return distinct deck names from cached notes.

#### Scenario: Return unique deck names
- **WHEN** `get_deck_names()` is called
- **THEN** the system returns a sorted list of unique deck names

### Requirement: Get last sync info
The system SHALL return the most recent sync log entry.

#### Scenario: Sync log exists
- **WHEN** `get_last_sync()` is called after at least one sync
- **THEN** the system returns the most recent `sync_log` row (id, synced_at, synced_at_epoch, total_cards, deck_count, new_cards, updated_cards)

#### Scenario: No previous sync
- **WHEN** `get_last_sync()` is called and no sync has occurred
- **THEN** the system returns None

### Requirement: Get total card count
The system SHALL return the total number of cards in the `notes` table.

#### Scenario: Cards exist
- **WHEN** `get_total_cards()` is called
- **THEN** the system returns the count of rows in the `notes` table

### Requirement: Get note by card_id
The system SHALL support retrieving a single note by its Anki card_id.

#### Scenario: Card exists
- **WHEN** `get_note_by_card_id(id)` is called with a valid card_id
- **THEN** the system returns the note row

#### Scenario: Card not found
- **WHEN** `get_note_by_card_id(id)` is called with a non-existent card_id
- **THEN** the system returns None
