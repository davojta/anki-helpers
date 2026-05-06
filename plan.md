# Plan: Sync Anki Notes to Local SQLite

## Goal

Mirror Anki notes into a local SQLite database via AnkiConnect.
Re-running the sync updates changed notes and removes deleted ones.

## Scope

- Read-only against Anki. Never write back.
- One deck or all decks, selectable by CLI flag.
- Notes only (not full review history).

## Schema

File: `anki.db` (path configurable, default `./anki.db`).

```sql
CREATE TABLE notes (
    note_id     INTEGER PRIMARY KEY,   -- Anki noteId
    model_name  TEXT    NOT NULL,
    deck_name   TEXT    NOT NULL,
    tags        TEXT    NOT NULL,      -- space-joined
    fields_json TEXT    NOT NULL,      -- {field_name: value}
    mod         INTEGER NOT NULL,      -- Anki mod timestamp
    synced_at   INTEGER NOT NULL       -- unix epoch of last sync
);

CREATE TABLE cards (
    card_id   INTEGER PRIMARY KEY,
    note_id   INTEGER NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
    deck_name TEXT    NOT NULL,
    due       INTEGER,
    interval  INTEGER,
    flags     INTEGER
);

CREATE TABLE sync_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

`sync_meta` stores `last_full_sync` (unix epoch) and `schema_version`.

## AnkiConnect Calls

| Step | Action          | Purpose                             |
|------|-----------------|-------------------------------------|
| 1    | `deckNames`     | Resolve deck filter.                |
| 2    | `findNotes`     | `deck:<name>` → note IDs.           |
| 3    | `notesInfo`     | Fields, tags, model, mod.           |
| 4    | `findCards`     | `nid:<id1,id2,...>` → card IDs.     |
| 5    | `cardsInfo`     | Deck, due, flags.                   |
| 6    | `getIntervals`  | Per-card interval.                  |

Batch IDs in chunks of 1000 to keep payloads small.

## Sync Algorithm

1. Open SQLite, run migrations (create tables if missing).
2. Fetch note IDs from Anki for the selected scope.
3. For each note from Anki:
   - `INSERT OR REPLACE` into `notes` if `mod` differs from stored `mod`.
4. Delete rows in `notes` whose `note_id` is not in the fetched set
   (cards cascade).
5. Replace `cards` rows for synced notes (delete + insert in one txn).
6. Update `sync_meta.last_full_sync`.
7. Print counts: inserted, updated, deleted, unchanged.

All steps run inside a single transaction. On error, roll back.

## CLI

New command in `src/anki_helpers/cli.py`:

```text
anki-helpers sync-db [--deck NAME] [--db PATH] [--dry-run] [--limit N]
```

- `--deck` filters to one deck. Omit for all decks.
- `--db` overrides `./anki.db`.
- `--dry-run` reports counts without writing.
- `--limit N` caps how many notes are synced (test/debug only).

## Quick Test (10 cards)

Smoke test the sync end-to-end with a tiny slice before trusting full runs.

1. Pick a deck with at least 10 notes (e.g. `deck:Default`).
2. Run a limited sync:

   ```bash
   anki-helpers sync-db --deck Default --limit 10 --db ./anki-test.db
   ```

   `--limit N` truncates the note ID list returned from `findNotes`
   to the first N before any further AnkiConnect calls. Test-only flag.

3. Expect output:

   ```text
   inserted: 10  updated: 0  deleted: 0  unchanged: 0
   ```

4. Verify row counts:

   ```bash
   sqlite3 anki-test.db "SELECT COUNT(*) FROM notes;"   # 10
   sqlite3 anki-test.db "SELECT COUNT(*) FROM cards;"   # >= 10
   ```

5. Re-run the same command. Expect `unchanged: 10`, all others 0.
6. Edit one note in Anki, re-run. Expect `updated: 1`.
7. Delete `anki-test.db` when done.

If any step fails, do not proceed to a full-deck sync.

## Files to Add

- `src/anki_helpers/db.py` — connection, migrations, upsert/delete helpers.
- `src/anki_helpers/sync.py` — orchestration (calls AnkiConnect + db).
- `tests/sync_test.py` — mocks AnkiConnect, asserts SQLite state.

## Out of Scope

- Two-way sync.
- Review history, scheduling state beyond `due`/`interval`.
- Media files.
