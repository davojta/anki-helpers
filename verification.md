# Verification: Anki → SQLite Sync

How a human checks the sync did the right thing.

## Prerequisites

- Anki is running with AnkiConnect installed.
- `sqlite3` CLI is available.
- `anki.db` exists after at least one `anki-helpers sync-db` run.

## 1. Counts Match

In Anki, open the browser, run query `deck:*`, note the count.
In SQLite:

```bash
sqlite3 anki.db "SELECT COUNT(*) FROM notes;"
```

Numbers should match (or match the deck filter you passed).

## 2. Spot-Check a Note

Pick any note in the Anki browser. Copy its note ID (Ctrl/Cmd+click → Info).

```bash
sqlite3 anki.db "SELECT deck_name, tags, fields_json
                 FROM notes WHERE note_id = <ID>;"
```

Compare:

- Deck name matches.
- Tags match (order may differ).
- Field values match what Anki shows (HTML preserved).

## 3. New Note Appears

1. Add a new note in Anki.
2. Re-run `anki-helpers sync-db`.
3. Output should report `inserted: 1`.
4. Confirm:

   ```bash
   sqlite3 anki.db "SELECT note_id FROM notes ORDER BY note_id DESC LIMIT 1;"
   ```

## 4. Edited Note Updates

1. Edit a field on any note in Anki.
2. Re-run sync.
3. Output should report `updated: 1`.
4. Query that `note_id` in SQLite — the field shows the new value.

## 5. Deleted Note Disappears

1. Delete a note in Anki.
2. Re-run sync.
3. Output should report `deleted: 1`.
4. Query the old `note_id` — returns no rows.
5. `cards` table has no rows for that `note_id` (cascade worked).

## 6. Cards Linked Correctly

```bash
sqlite3 anki.db "SELECT n.note_id, COUNT(c.card_id)
                 FROM notes n LEFT JOIN cards c USING(note_id)
                 GROUP BY n.note_id HAVING COUNT(c.card_id) = 0;"
```

Should be empty. Every note has at least one card.

## 7. Idempotent Re-run

Run `anki-helpers sync-db` twice in a row without touching Anki.
Second run should report `inserted: 0, updated: 0, deleted: 0`.

## 8. Dry Run Writes Nothing

```bash
cp anki.db anki.db.bak
anki-helpers sync-db --dry-run
diff <(sqlite3 anki.db .dump) <(sqlite3 anki.db.bak .dump)
```

Diff should be empty.

## Pass Criteria

All eight checks pass. If any fails, the sync is not trustworthy yet.
