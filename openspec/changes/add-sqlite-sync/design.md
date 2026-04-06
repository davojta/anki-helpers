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
- `note_id` (INTEGER) — Anki note ID (for write-back)
- `card_id` (INTEGER PK) — Anki card ID (for write-back)
- `deck_name` (TEXT)
- `fields` (TEXT, JSON)
- `tags` (TEXT, JSON)
- `due` (INTEGER)
- `interval` (INTEGER)
- `flag` (INTEGER)
- `due_query` (INTEGER) — set to the `due` value from `cardsInfo`
- `modified` (INTEGER) — Anki note modification epoch (from `notesInfo.mod`)

**`sync_log` table columns**:
- `id` (INTEGER PK, autoincrement) — sync ID
- `synced_at` (TEXT, ISO timestamp) — human-readable timestamp
- `synced_at_epoch` (INTEGER) — epoch seconds (used for incremental sync comparison)
- `total_cards` (INTEGER) — total cards in cache after sync
- `deck_count` (INTEGER) — number of distinct decks (stacks)
- `new_cards` (INTEGER) — number of cards inserted (not previously in cache)
- `updated_cards` (INTEGER) — number of existing cards updated

**Rationale**: The `synced_at_epoch` column enables precise incremental sync by comparing against Anki's `notesInfo.mod` epoch timestamps. The `updated_cards` column distinguishes between newly inserted and re-updated cards, giving a complete picture of each sync's impact.

### 3. Full sync of all cards (not just red-flagged)

**Choice**: The `sync` command fetches ALL notes and cards from Anki, not just red-flagged ones.
**Alternatives**: Sync only red-flagged cards.
**Rationale**: A complete cache enables offline browsing of all cards, future features like deck analytics, and avoids the need to re-sync when new query types are added. The dataset is small (hundreds to low thousands of cards), so there's no performance penalty.

### 4. Simplified due_query from cardsInfo

**Choice**: Use the `due` field directly from AnkiConnect's `cardsInfo` response as `due_query`.
**Alternatives**: Replicate the expensive per-day query logic (~32 `findNotes` calls).
**Rationale**: The `due` field from `cardsInfo` is an integer representing the card's due day. This provides the same ordering information as the current multi-query approach, but in a single API call.

### 5. Initial load + incremental updates

**Choice**: Two sync modes:
- **Initial sync** (no previous sync_log entry): Full load — fetch all notes and cards, `replace_all` into SQLite.
- **Incremental sync** (previous sync exists): Fetch only notes modified since `last synced_at_epoch`, then `upsert_notes` (insert new cards, update existing cards).

**Incremental sync algorithm**:
1. Read `synced_at_epoch` from the most recent sync_log row
2. Calculate days since last sync: `ceil((now_epoch - synced_at_epoch) / 86400) + 1` (safety margin)
3. Call `findNotes("prop:mod:N")` with N = calculated days → returns recently modified note IDs
4. Call `notesInfo` for those note IDs → filter client-side to `mod > synced_at_epoch`
5. For filtered notes, get their card IDs → call `cardsInfo`
6. Transform to notes rows → `upsert_notes` (INSERT OR REPLACE by card_id)
7. Record sync_log entry

**Alternatives**: Full replacement on every sync (wasteful, risky — always deletes everything even if little changed).
**Rationale**: Incremental sync is faster (only fetches changed notes) and safer (never deletes the entire cache). The `upsert_notes` method preserves existing data that hasn't changed. `replace_all` is reserved for the initial load when the cache is empty.

### 6. New module `sqlite_storage.py` for database layer

**Choice**: Separate module with `SQLiteStorage` class handling connection, schema init, and queries.
**Rationale**: Clean separation from AnkiConnect client. Easy to test with in-memory SQLite.

### 7. `--local` flag on existing commands

**Choice**: Add `--local` boolean flag to `list-red-flags` and `get-examples-for-red-flags-cards` that reads from SQLite instead of calling AnkiConnect.
**Rationale**: Backward-compatible. Default behavior unchanged.

## Risks / Trade-offs

- **Deleted cards not detected**: Incremental sync fetches modified notes but doesn't detect cards deleted in Anki → acceptable for now; a `sync --full` flag can be added later to force a full reload
- **Stale data**: Cache can become outdated → mitigate with sync_log timestamp and warning when data is older than 24 hours
- **Schema migration**: Future schema changes need migration strategy → start simple, add migration when needed
- **Write-back scope**: Current design stores IDs for future write-back but doesn't implement it yet → document clearly, implement in a follow-up change
- **due_query approximation**: The `due` field from `cardsInfo` may differ slightly from the per-day query results in edge cases → functionally equivalent for sorting purposes
