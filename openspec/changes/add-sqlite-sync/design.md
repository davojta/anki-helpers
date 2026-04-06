## Context

The anki-helpers CLI currently makes direct AnkiConnect API calls for every command. Each invocation requires Anki to be running and involves multiple round-trips (e.g., `find_cards_with_red_flag_sorted` makes ~32 API calls for due-query lookups). This limits the tool to online-only use and makes repeated queries slow.

## Goals / Non-Goals

**Goals:**
- Cache ALL Anki card and note data in a local SQLite database (not just red-flagged)
- Provide a `sync` command to pull fresh data from Anki — initial full load, then incremental updates
- Store Anki note_id and card_id locally to enable updating individual cards in Anki
- Track sync history with statistics (total cards, deck count, new cards)
- Allow existing commands to read from cache via `--local` flag
- Keep the SQLite layer simple and maintainable

**Non-Goals:**
- Automatic real-time sync or change detection (explicit `sync` command)
- Full Anki schema replication — only store data needed by current and planned commands
- Multi-database or remote SQLite support
- Conflict resolution for concurrent edits
- Handling cards/notes deleted in Anki since last sync (future consideration)

## Decisions

### 1. Single SQLite database file in project root

**Choice**: `.anki-cache.db` in the project directory.
**Alternatives**: XDG data dir, user config dir.
**Rationale**: Simple, portable, easy to inspect/delete. Keeps project self-contained.

### 2. Two-table schema: `notes` and `sync_log`

**Choice**: A flat `notes` table storing card data with Anki note_id and card_id as the link back to Anki, and a `sync_log` table recording each sync operation with statistics.

**`notes` table columns**:
- `note_id` (INTEGER) — from `cardsInfo.note` (parent note ID, for write-back)
- `card_id` (INTEGER PK) — from `cardsInfo.cardId` (for write-back)
- `deck_name` (TEXT) — from `cardsInfo.deckName`
- `fields` (TEXT, JSON) — from `notesInfo.fields` (field name → value mapping, serialized as JSON)
- `tags` (TEXT, JSON) — from `notesInfo.tags` (list, serialized as JSON)
- `due` (INTEGER) — raw `due` from `cardsInfo` (meaning depends on `queue` type)
- `interval` (INTEGER) — from `cardsInfo.interval`
- `flag` (INTEGER) — from `cardsInfo.flags` (0-7 bitmask, Anki field is `flags` plural)
- `queue` (INTEGER) — from `cardsInfo.queue` (needed to interpret `due` correctly)
- `due_query` (INTEGER) — converted relative days for sorting (see decision #4)
- `modified` (INTEGER) — from `notesInfo.mod` (Unix epoch seconds)

**`sync_log` table columns**:
- `id` (INTEGER PK, autoincrement) — sync ID
- `synced_at` (TEXT, ISO timestamp) — human-readable timestamp
- `synced_at_epoch` (INTEGER) — epoch seconds (used for incremental sync comparison)
- `total_cards` (INTEGER) — total cards in cache after sync
- `deck_count` (INTEGER) — number of distinct decks (stacks)
- `new_cards` (INTEGER) — number of cards inserted (not previously in cache)
- `updated_cards` (INTEGER) — number of existing cards updated

**Rationale**: Added `queue` column because the raw `due` value's meaning depends on queue type (new=ordinal, learn=unix timestamp, review=days since collection creation). Storing `queue` allows correct interpretation of `due` at query time. The `flag` column stores the raw Anki `flags` value (0-7); the `notesInfo` field name is `noteId` but `cardsInfo` uses `note` for the parent note ID.

### 3. Full sync of all cards (not just red-flagged)

**Choice**: The `sync` command fetches ALL notes and cards from Anki, not just red-flagged ones.
**Alternatives**: Sync only red-flagged cards.
**Rationale**: A complete cache enables offline browsing of all cards, future features like deck analytics, and avoids the need to re-sync when new query types are added. The dataset is small (hundreds to low thousands of cards), so there's no performance penalty.

### 4. due_query conversion from raw due field

**Choice**: Convert the raw `due` field from `cardsInfo` to a relative-days value for sorting, based on queue type:
- **Review cards** (queue 2): `due_query = raw_due - days_elapsed` (relative days from today, negative = overdue)
- **Day-learn cards** (queue 3): same conversion as review
- **New cards** (queue 0): `due_query = raw_due` (ordinal position, already relative)
- **Learning cards** (queue 1): `due_query = raw_due` (Unix timestamp, sorts chronologically)
- **Preview repeat** (queue 4): `due_query = raw_due` (Unix timestamp)

The `days_elapsed` value (days since collection creation) is determined once per sync by finding a card where `prop:due=0` and reading its raw `due` value (per the API doc's recommendation).

**Alternatives**: Store raw `due` without conversion (sorting is incorrect for review cards — absolute days, not relative); replicate the expensive per-day query logic (~32 `findNotes` calls).
**Rationale**: The conversion produces correct relative-day values for the common case (review cards) and preserves the existing sort behavior. It replaces the current ~32-call approach with a single API call for `days_elapsed` determination.

### 5. Initial load + incremental updates

**Choice**: Two sync modes:
- **Initial sync** (no previous sync_log entry): Full load — fetch all notes and cards, `replace_all` into SQLite.
- **Incremental sync** (previous sync exists): Fetch only notes modified since `last synced_at_epoch`, then `upsert_notes` (insert new cards, update existing cards).

**Initial sync API sequence** (3 calls):
1. `notesInfo(query="")` → all note data (fields, tags, mod, cards list). Eliminates separate `findNotes` call.
2. `cardsInfo(cards=all_card_ids_from_notes)` → all card data (deck, due, interval, flags, queue)
3. `findCards("prop:due=0", limit=1)` → determine `days_elapsed` for due_query conversion

**Incremental sync algorithm** (uses `edited:N` search — there is no `prop:mod` operator):
1. Read `synced_at_epoch` from the most recent sync_log row
2. Calculate days since last sync: `max(1, ceil((now_epoch - synced_at_epoch) / 86400) + 1)` (safety margin)
3. Call `findNotes("edited:N")` with N = calculated days → returns recently modified note IDs
4. Call `notesInfo(notes=note_ids)` → filter client-side to `mod > synced_at_epoch` (precision filter)
5. For filtered notes, collect card IDs from `notesInfo.cards` field → call `cardsInfo`
6. Determine `days_elapsed` (may be cached from initial sync)
7. Transform to notes rows → `upsert_notes` (INSERT OR REPLACE by card_id)
8. Record sync_log entry

**Alternatives**: Full replacement on every sync (wasteful, risky — always deletes everything even if little changed); using `prop:mod:N` for incremental queries (this operator does not exist in Anki's search syntax).
**Rationale**: `notesInfo(query="")` accepts a search query parameter, eliminating the need for a separate `findNotes` call. `notesInfo` also returns a `cards` field with card IDs per note, providing the link between notes and cards without an extra `findCards` call. The `edited:N` operator is the correct way to find recently modified notes — it filters by note `mod` timestamp relative to the scheduler day boundary.

### 6. New module `sqlite_storage.py` for database layer

**Choice**: Separate module with `SQLiteStorage` class handling connection, schema init, and queries.
**Rationale**: Clean separation from AnkiConnect client. Easy to test with in-memory SQLite.

### 7. `--local` flag on existing commands

**Choice**: Add `--local` boolean flag to `list-red-flags` and `get-examples-for-red-flags-cards` that reads from SQLite instead of calling AnkiConnect.
**Rationale**: Backward-compatible. Default behavior unchanged.

### 8. `query-local` command for raw SQL inspection

**Choice**: Add `query-local SQL` command that executes arbitrary SQL against `.anki-cache.db` and prints results in table format.
**Example**: `anki-helpers query-local "SELECT COUNT(*) FROM notes;"`
**Rationale**: Essential for manual validation and debugging. Lets developers inspect cached data without installing sqlite3 CLI. No filtering/sorting flags needed — the user writes raw SQL.

### 9. `query-anki` command with filter/sort DSL

**Choice**: Add `query-anki list` subcommand with `--filter` and `--sort` options that queries Anki directly via AnkiConnect.

**Filter syntax**: `--filter key=value` with `:` separator for multiple filters. Supported filters:
| Filter | Example | Anki search |
|--------|---------|-------------|
| `flag=red` | `--filter flag=red` | `flag:1` |
| `flag=orange` | `--filter flag=orange` | `flag:2` |
| `flag=green` | `--filter flag=green` | `flag:3` |
| `flag=blue` | `--filter flag=blue` | `flag:4` |
| `flag=pink` | `--filter flag=pink` | `flag:5` |
| `flag=turquoise` | `--filter flag=turquoise` | `flag:6` |
| `flag=purple` | `--filter flag=purple` | `flag:7` |
| `flag=none` | `--filter flag=none` | `flag:0` |
| `due_date=<Nd` | `--filter due_date=<10d` | `prop:due<10` |
| `due_date=>Nd` | `--filter due_date=>5d` | `prop:due>5` |

Multiple filters: `--filter flag=red:due_date=<10d` → combined with AND logic.

**Sort options**: `--sort due` (ascending by due date), `--sort interval` (ascending by interval).

**Rationale**: Provides a general-purpose query interface for Anki without requiring a prior sync. The filter DSL is simple and maps directly to Anki's search syntax. The `list` subcommand leaves room for future subcommands (e.g., `count`, `update`). Anki supports 7 flag colors (red, orange, green, blue, pink, turquoise, purple) plus none.

**Alternatives**: Expose raw Anki search queries directly (too fragile, requires user to know Anki's search syntax).

## Risks / Trade-offs

- **Deleted cards not detected**: Incremental sync fetches modified notes but doesn't detect cards deleted in Anki → acceptable for now; a `sync --full` flag can be added later to force a full reload
- **Stale data**: Cache can become outdated → mitigate with sync_log timestamp and warning when data is older than 24 hours
- **Schema migration**: Future schema changes need migration strategy → start simple, add migration when needed
- **Write-back scope**: Current design stores IDs for future write-back but doesn't implement it yet → document clearly, implement in a follow-up change
- **due_query for non-review cards**: New and learning cards have different `due` semantics → handled by queue-type-aware conversion; new cards use ordinal position, learning cards use Unix timestamp
- **days_elapsed caching**: The collection creation offset could change if Anki switches profiles → re-fetch on each sync (lightweight: single `prop:due=0` query)
