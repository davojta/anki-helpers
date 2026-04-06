## Why

Every CLI command currently makes live AnkiConnect API calls, which requires Anki to be running and adds network latency. A local SQLite cache of Anki card data would enable faster queries, offline browsing, and serve as a foundation for future features like analytics or batch processing.

Additionally, storing Anki IDs locally enables modifying cached data and pushing individual card updates back to Anki, making the cache a two-way sync layer rather than a read-only snapshot.

## What Changes

- Add a SQLite database layer to cache Anki card and note data locally
- Add a `sync` CLI command that pulls card data from Anki via AnkiConnect into SQLite
- Store Anki note and card IDs in the local database to enable write-back of individual card updates
- Track sync history in a dedicated `sync_log` table with summary statistics
- Refactor existing commands (`list-red-flags`, `get-examples-for-red-flags-cards`) to optionally read from the SQLite cache instead of making live API calls
- Add a `--local` flag to relevant commands to use cached data

## Capabilities

### New Capabilities
- `sqlite-storage`: Local SQLite database schema, connection management, and CRUD operations for cached Anki data. Two tables: `notes` (full card/note data with Anki IDs for write-back) and `sync_log` (sync history with statistics).
- `anki-sync`: Sync command and logic to pull card/note data from AnkiConnect into the local SQLite store, recording sync metadata (total cards, deck count, new card count).
- `query-local`: CLI command to run arbitrary SQL queries against the local `.anki-cache.db` for inspection and debugging.
- `query-anki`: CLI command to query Anki directly via AnkiConnect with `--filter` and `--sort` options, without requiring a prior sync.

### Modified Capabilities
- _(none — existing commands gain optional `--local` flag but behavior is backward-compatible)_

## Impact

- **New dependency**: `sqlite3` (stdlib — no external dependency)
- **New files**: SQLite storage module, sync command, migration/schema definition
- **Modified files**: `cli.py` (add sync, query-local, query-anki commands; add `--local` flag), tests
- **Storage**: SQLite database file in project directory (e.g., `.anki-cache.db`)
