## 1. AnkiConnect — new methods for sync and query

- [ ] 1.1 Add `get_all_notes_info()` — calls `notesInfo(query="")` to get all notes in one call (includes fields, tags, mod, cards list)
- [ ] 1.2 Add `get_cards_info(card_ids)` — calls `cardsInfo(cards=card_ids)`
- [ ] 1.3 Add `find_edited_notes(days)` — calls `findNotes("edited:N")` for recently modified notes
- [ ] 1.4 Add `find_notes_info(note_ids)` — calls `notesInfo(notes=note_ids)` for specific note IDs
- [ ] 1.5 Add `find_cards(query)` — calls `findCards(query)` for arbitrary search queries
- [ ] 1.6 Add `get_days_elapsed()` — calls `findCards("prop:due=0")`, reads raw `due` from a returned card as `days_elapsed`

## 2. SQLite Storage Module

- [ ] 2.1 Create `src/anki_helpers/sqlite_storage.py` with `SQLiteStorage` class — init, schema creation (notes + sync_log tables), context manager
- [ ] 2.2 Implement `replace_all(notes)` — atomic DELETE + INSERT in a transaction; rollback on failure; for initial load only
- [ ] 2.3 Implement `upsert_notes(notes)` — INSERT OR REPLACE by card_id; atomic; returns (new_count, updated_count)
- [ ] 2.4 Implement `add_sync_log(total_cards, deck_count, new_cards, updated_cards)` — insert sync_log entry with UTC ISO timestamp and epoch
- [ ] 2.5 Implement `get_cards_by_flag(flag)` — query notes filtered by flag value, sorted by due_query ascending
- [ ] 2.6 Implement `get_deck_names()` — distinct deck names, sorted
- [ ] 2.7 Implement `get_last_sync()` — most recent sync_log row
- [ ] 2.8 Implement `get_total_cards()` — count of rows in notes table
- [ ] 2.9 Implement `get_note_by_card_id(card_id)` — single-card lookup
- [ ] 2.10 Implement `execute_sql(sql)` — read-only SQL execution, rejects non-SELECT statements, returns list[dict]

## 3. Data Transformation

- [ ] 3.1 Implement `notes_info` → notes row: extract noteId, fields (JSON), tags (JSON), mod, cards list
- [ ] 3.2 Implement `cards_info` → notes row: extract cardId, note (parent note ID), deckName, due, interval, flags (as `flag`), queue, mod
- [ ] 3.3 Implement `due_query` conversion: for review/relearning cards (queue 2,3): `due_query = raw_due - days_elapsed`; for new cards (queue 0): `due_query = raw_due`; for learning cards (queue 1): `due_query = raw_due`
- [ ] 3.4 Implement merge: join notesInfo data with cardsInfo data by note_id → card_id mapping (from notesInfo.cards field)

## 4. Sync Command

- [ ] 4.1 Add `sync` CLI command in `cli.py`
- [ ] 4.2 Implement sync mode detection: check sync_log for previous sync → choose initial or incremental path
- [ ] 4.3 Initial sync orchestration: notesInfo(query="") → collect card IDs from notes → cardsInfo → determine days_elapsed → transform → replace_all
- [ ] 4.4 Incremental sync orchestration: get_last_sync → calculate days → find_edited_notes → find_notes_info → filter by mod epoch → collect card IDs → cardsInfo → determine days_elapsed → transform → upsert_notes
- [ ] 4.5 Print sync summary: mode (initial/incremental), timestamp, total cards, decks, new cards, updated cards
- [ ] 4.6 Error handling: AnkiConnect unavailability, partial fetch failure (exit without modifying DB)

## 5. query-local Command

- [ ] 5.1 Add `query-local` CLI command in `cli.py` — takes SQL string argument
- [ ] 5.2 Route to `SQLiteStorage.execute_sql(sql)`, print results as table
- [ ] 5.3 Error handling: no database file, invalid SQL, non-SELECT statement

## 6. query-anki Command

- [ ] 6.1 Add `query-anki` Click group with `list` subcommand in `cli.py`
- [ ] 6.2 Implement filter parser: parse `key=value` pairs with `:` separator, validate keys (flag, due_date) and values
- [ ] 6.3 Implement filter-to-search translator: `flag=red` → `flag:1`, `flag=orange` → `flag:2`, `flag=green` → `flag:3`, `flag=blue` → `flag:4`, `flag=pink` → `flag:5`, `flag=turquoise` → `flag:6`, `flag=purple` → `flag:7`, `flag=none` → `flag:0`; `due_date=<10d` → `prop:due<10`
- [ ] 6.4 Implement query execution: build Anki search string → findCards → cardsInfo → notesInfo → format output
- [ ] 6.5 Implement sort: `--sort due` (default), `--sort interval`
- [ ] 6.6 Print results as table: card_id, note_id, deck, due, flag, fields summary, tags
- [ ] 6.7 Error handling: unknown filter key, invalid filter value, Anki not running

## 7. Local Flag Integration

- [ ] 7.1 Add `--local` flag to `list-red-flags` command, routing to SQLiteStorage.get_cards_by_flag(1) when set
- [ ] 7.2 Add `--local` flag to `get-examples-for-red-flags-cards` command
- [ ] 7.3 Add stale data warning when get_last_sync() is older than 24 hours
- [ ] 7.4 Add "no cached data" warning when `--local` is used and get_last_sync() returns None

## 8. Tests

- [ ] 8.1 Unit tests for `SQLiteStorage` using in-memory SQLite (init, replace_all, upsert_notes, queries, sync_log, atomicity on failure)
- [ ] 8.2 Unit tests for upsert_notes: mix of new/existing, all new, all existing, empty input
- [ ] 8.3 Unit tests for sync_log: add entry, get_last_sync, epoch/ISO timestamp format
- [ ] 8.4 Unit tests for data transformation: notesInfo + cardsInfo → notes rows, due_query conversion per queue type
- [ ] 8.5 Unit tests for sync mode detection: first sync → initial, subsequent → incremental
- [ ] 8.6 Unit tests for filter parser: single filter, multiple filters, unknown key, invalid value
- [ ] 8.7 Unit tests for filter-to-search translation: all 8 flag colors, due_date operators
- [ ] 8.8 Unit tests for execute_sql: valid SELECT, non-SELECT rejection
- [ ] 8.9 Unit tests for due_query conversion: review cards (queue=2, relative days), new cards (queue=0, ordinal), learning cards (queue=1, timestamp)
- [ ] 8.10 Integration test for initial sync command (mocked AnkiConnect, real SQLite)
- [ ] 8.11 Integration test for incremental sync command (mocked AnkiConnect, pre-populated SQLite)
- [ ] 8.12 Integration tests for `query-local` command (with pre-populated SQLite)
- [ ] 8.13 Integration tests for `query-anki list` command (mocked AnkiConnect)
- [ ] 8.14 Integration tests for `--local` flag on `list-red-flags` and `get-examples-for-red-flags-cards`
- [ ] 8.15 Unit tests for new AnkiConnect methods (get_all_notes_info, get_cards_info, find_edited_notes, get_days_elapsed)

## 9. E2E Tests (requires RUN_E2E_TESTS=1 and running Anki)

- [ ] 9.1 E2E: `sync` initial load → verify `.anki-cache.db` created with correct row counts
- [ ] 9.2 E2E: `sync` incremental → modify card in Anki → re-sync → verify updated count
- [ ] 9.3 E2E: `query-local "SELECT COUNT(*) FROM notes;"` → matches Anki card count
- [ ] 9.4 E2E: `query-anki list --filter flag=red --sort due` → output matches `list-red-flags --local`
- [ ] 9.5 E2E: `query-anki list --filter due_date=<10d --sort due` → returns only cards due within 10 days
- [ ] 9.6 E2E: `query-anki list --filter flag=red:due_date=<10d --sort due` → combined filter
