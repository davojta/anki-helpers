## 1. AnkiConnect — new methods for full sync

- [ ] 1.1 Add `get_all_note_ids()` — calls `findNotes` with query `""`
- [ ] 1.2 Add `get_all_card_ids()` — calls `findCards` with query `""`
- [ ] 1.3 Add `get_notes_info(note_ids)` — calls `notesInfo` with note IDs, returns list with `mod` epoch
- [ ] 1.4 Add `get_cards_info(card_ids)` — calls `cardsInfo` with card IDs
- [ ] 1.5 Add `find_notes_modified_since(days)` — calls `findNotes("prop:mod:N")` for incremental sync

## 2. SQLite Storage Module

- [ ] 2.1 Create `src/anki_helpers/sqlite_storage.py` with `SQLiteStorage` class — init, schema creation (notes + sync_log tables), context manager
- [ ] 2.2 Implement `replace_all(notes)` — atomic DELETE + INSERT in a transaction; rollback on failure; for initial load only
- [ ] 2.3 Implement `upsert_notes(notes)` — INSERT OR REPLACE by card_id; atomic; returns (new_count, updated_count)
- [ ] 2.4 Implement `add_sync_log(total_cards, deck_count, new_cards, updated_cards)` — insert sync_log entry with UTC ISO timestamp and epoch
- [ ] 2.5 Implement `get_cards_by_flag(flag)` — query notes filtered by flag, sorted by due_query ascending
- [ ] 2.6 Implement `get_deck_names()` — distinct deck names, sorted
- [ ] 2.7 Implement `get_last_sync()` — most recent sync_log row
- [ ] 2.8 Implement `get_total_cards()` — count of rows in notes table
- [ ] 2.9 Implement `get_note_by_card_id(card_id)` — single-card lookup
- [ ] 2.10 Implement `execute_sql(sql)` — read-only SQL execution, rejects non-SELECT statements, returns list[dict]

## 3. Sync Command

- [ ] 3.1 Add `sync` CLI command in `cli.py`
- [ ] 3.2 Implement sync mode detection: check sync_log for previous sync → choose initial or incremental path
- [ ] 3.3 Initial sync orchestration: get_all_note_ids → get_notes_info → get_all_card_ids → get_cards_info → transform → replace_all
- [ ] 3.4 Incremental sync orchestration: get_last_sync → calculate days since last sync → find_notes_modified_since → get_notes_info → filter by mod epoch → get cards → get_cards_info → transform → upsert_notes
- [ ] 3.5 Transform: AnkiConnect responses → notes rows (due_query = due from cardsInfo, modified = mod from notesInfo)
- [ ] 3.6 Print sync summary: mode (initial/incremental), timestamp, total cards, decks, new cards, updated cards
- [ ] 3.7 Error handling: AnkiConnect unavailability, partial fetch failure (exit without modifying DB)

## 4. query-local Command

- [ ] 4.1 Add `query-local` CLI command in `cli.py` — takes SQL string argument
- [ ] 4.2 Route to `SQLiteStorage.execute_sql(sql)`, print results as table
- [ ] 4.3 Error handling: no database file, invalid SQL, non-SELECT statement

## 5. query-anki Command

- [ ] 5.1 Add `query-anki` Click group with `list` subcommand in `cli.py`
- [ ] 5.2 Implement filter parser: parse `key=value` pairs with `:` separator, validate keys (flag, due_date) and values
- [ ] 5.3 Implement filter-to-search translator: `flag=red` → `flag:1`, `due_date=<10d` → `prop:due<10`
- [ ] 5.4 Implement query execution: build Anki search string → findCards → cardsInfo → notesInfo → format output
- [ ] 5.5 Implement sort: `--sort due` (default), `--sort interval`
- [ ] 5.6 Print results as table: card_id, note_id, deck, due, flag, fields summary, tags
- [ ] 5.7 Error handling: unknown filter key, invalid filter value, Anki not running

## 6. Local Flag Integration

- [ ] 6.1 Add `--local` flag to `list-red-flags` command, routing to SQLiteStorage.get_cards_by_flag(1) when set
- [ ] 6.2 Add `--local` flag to `get-examples-for-red-flags-cards` command
- [ ] 6.3 Add stale data warning when get_last_sync() is older than 24 hours
- [ ] 6.4 Add "no cached data" warning when `--local` is used and get_last_sync() returns None

## 7. Tests

- [ ] 7.1 Unit tests for `SQLiteStorage` using in-memory SQLite (init, replace_all, upsert_notes, queries, sync_log, atomicity on failure)
- [ ] 7.2 Unit tests for upsert_notes: mix of new/existing, all new, all existing, empty input
- [ ] 7.3 Unit tests for sync_log: add entry, get_last_sync, epoch/ISO timestamp format
- [ ] 7.4 Unit tests for data transformation: AnkiConnect response → notes row format
- [ ] 7.5 Unit tests for sync mode detection: first sync → initial, subsequent → incremental
- [ ] 7.6 Unit tests for filter parser: single filter, multiple filters, unknown key, invalid value
- [ ] 7.7 Unit tests for filter-to-search translation: all supported keys/values
- [ ] 7.8 Unit tests for execute_sql: valid SELECT, non-SELECT rejection
- [ ] 7.9 Integration test for initial sync command (mocked AnkiConnect, real SQLite)
- [ ] 7.10 Integration test for incremental sync command (mocked AnkiConnect, pre-populated SQLite)
- [ ] 7.11 Integration tests for `query-local` command (with pre-populated SQLite)
- [ ] 7.12 Integration tests for `query-anki list` command (mocked AnkiConnect)
- [ ] 7.13 Integration tests for `--local` flag on `list-red-flags` and `get-examples-for-red-flags-cards`
- [ ] 7.14 Unit tests for new AnkiConnect methods (get_all_note_ids, get_all_card_ids, get_notes_info, get_cards_info, find_notes_modified_since)

## 8. E2E Tests (requires RUN_E2E_TESTS=1 and running Anki)

- [ ] 8.1 E2E: `sync` initial load → verify `.anki-cache.db` created with correct row counts
- [ ] 8.2 E2E: `sync` incremental → modify card in Anki → re-sync → verify updated count
- [ ] 8.3 E2E: `query-local "SELECT COUNT(*) FROM notes;"` → matches Anki card count
- [ ] 8.4 E2E: `query-anki list --filter flag=red --sort due` → output matches `list-red-flags --local`
- [ ] 8.5 E2E: `query-anki list --filter due_date=<10d --sort due` → returns only cards due within 10 days
- [ ] 8.6 E2E: `query-anki list --filter flag=red:due_date=<10d --sort due` → combined filter
