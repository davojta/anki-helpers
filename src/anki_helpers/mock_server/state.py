"""SQLite-backed state for the AnkiConnect mock server.

The schema mirrors a small subset of Anki's collection.anki2 layout
(decks, models, notes, cards, media) so that tests can assert against
the database directly. All filtering happens in Python rather than via
the JSON1 SQLite extension to avoid a hard dependency on it.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_DECK_ID = 1
DEFAULT_DECK_NAME = "Default"
DEFAULT_MODEL_ID = 1607392319
DEFAULT_MODEL_NAME = "Basic"
DEFAULT_MODEL_FIELDS = ["Front", "Back"]
DEFAULT_MODEL_TEMPLATES = [
    {
        "Name": "Card 1",
        "Front": "{{Front}}",
        "Back": "{{FrontSide}}<hr id=answer>{{Back}}",
    }
]


class State:
    """SQLite-backed state container for the mock server."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize state with a SQLite database.

        Args:
            db_path: Filesystem path or ``:memory:`` for an in-memory database.
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(
            db_path, isolation_level=None, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and seed default deck/model if missing."""
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS decks (
                id   INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS models (
                id             INTEGER PRIMARY KEY,
                name           TEXT UNIQUE NOT NULL,
                fields_json    TEXT NOT NULL,
                templates_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY,
                model_id    INTEGER NOT NULL REFERENCES models(id),
                deck_id     INTEGER NOT NULL REFERENCES decks(id),
                fields_json TEXT NOT NULL,
                tags_json   TEXT NOT NULL DEFAULT '[]',
                mod         INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id        INTEGER PRIMARY KEY,
                note_id   INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                deck_id   INTEGER NOT NULL REFERENCES decks(id),
                ord       INTEGER NOT NULL DEFAULT 0,
                queue     INTEGER NOT NULL DEFAULT 0,
                due       INTEGER NOT NULL DEFAULT 0,
                ivl       INTEGER NOT NULL DEFAULT 0,
                factor    INTEGER NOT NULL DEFAULT 2500,
                reps      INTEGER NOT NULL DEFAULT 0,
                lapses    INTEGER NOT NULL DEFAULT 0,
                flags     INTEGER NOT NULL DEFAULT 0,
                suspended INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS media (
                filename TEXT PRIMARY KEY,
                data     BLOB NOT NULL
            );
            """
        )
        if not self.db.execute("SELECT 1 FROM decks").fetchone():
            self.db.execute(
                "INSERT INTO decks(id, name) VALUES (?, ?)",
                (DEFAULT_DECK_ID, DEFAULT_DECK_NAME),
            )
        if not self.db.execute("SELECT 1 FROM models").fetchone():
            self.db.execute(
                "INSERT INTO models(id, name, fields_json, templates_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    DEFAULT_MODEL_ID,
                    DEFAULT_MODEL_NAME,
                    json.dumps(DEFAULT_MODEL_FIELDS),
                    json.dumps(DEFAULT_MODEL_TEMPLATES),
                ),
            )

    def reset(self) -> None:
        """Wipe all user data, restoring only the default deck and model."""
        with self._lock:
            self.db.executescript(
                """
                DELETE FROM cards;
                DELETE FROM notes;
                DELETE FROM media;
                DELETE FROM decks WHERE id <> {default_deck};
                DELETE FROM models WHERE id <> {default_model};
                """.format(
                    default_deck=DEFAULT_DECK_ID,
                    default_model=DEFAULT_MODEL_ID,
                )
            )

    def next_id(self, used_ids: Iterable[int]) -> int:
        """Return a fresh millisecond-timestamp id, incrementing on collision.

        Args:
            used_ids: Iterable of ids already taken in the target table.

        Returns:
            A unique integer id (Unix epoch ms, possibly bumped).
        """
        seen = set(used_ids)
        candidate = int(time.time() * 1000)
        while candidate in seen:
            candidate += 1
        return candidate

    def get_deck_id(self, name: str) -> Optional[int]:
        """Look up a deck id by name.

        Args:
            name: Deck name to look up.

        Returns:
            Deck id if the deck exists, else ``None``.
        """
        row = self.db.execute("SELECT id FROM decks WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None

    def get_or_create_deck(self, name: str) -> int:
        """Return the id of a deck by name, creating it if it does not exist.

        Args:
            name: Deck name to look up or create.

        Returns:
            Deck id.
        """
        existing = self.get_deck_id(name)
        if existing is not None:
            return existing
        used = {row["id"] for row in self.db.execute("SELECT id FROM decks")}
        new_id = self.next_id(used)
        with self._lock:
            self.db.execute("INSERT INTO decks(id, name) VALUES (?, ?)", (new_id, name))
        return new_id

    def get_model(self, name: str) -> Optional[sqlite3.Row]:
        """Look up a model by name.

        Args:
            name: Model name.

        Returns:
            The matching row, or ``None`` if no model has that name.
        """
        return self.db.execute(
            "SELECT * FROM models WHERE name = ?", (name,)
        ).fetchone()

    def add_note(
        self,
        deck_name: str,
        model_name: str,
        fields: Dict[str, str],
        tags: Optional[List[str]] = None,
        allow_duplicate: bool = False,
    ) -> int:
        """Insert a note (and a single card) into the mock database.

        Args:
            deck_name: Target deck name; must already exist.
            model_name: Note type name; must already exist.
            fields: Field name to value mapping.
            tags: Optional list of tags.
            allow_duplicate: When ``False``, raise on first-field duplicates.

        Returns:
            The new note id.

        Raises:
            ValueError: If the deck/model is missing, the first field is
                empty, or a duplicate is detected and not allowed.
        """
        deck_id = self.get_deck_id(deck_name)
        if deck_id is None:
            raise ValueError(f"deck was not found: {deck_name}")
        model = self.get_model(model_name)
        if model is None:
            raise ValueError(f"model was not found: {model_name}")
        field_order = json.loads(model["fields_json"])
        first_field_name = field_order[0]
        first_field_value = (fields.get(first_field_name) or "").strip()
        if not first_field_value:
            raise ValueError("cannot create note because it is empty")
        if not allow_duplicate and self._has_duplicate_first_field(
            deck_id, model["id"], first_field_name, first_field_value
        ):
            raise ValueError("cannot create note because it is a duplicate")
        used_ids = self._used_object_ids()
        note_id = self.next_id(used_ids)
        used_ids.add(note_id)
        card_id = self.next_id(used_ids)
        with self._lock:
            self.db.execute(
                "INSERT INTO notes(id, model_id, deck_id, fields_json, "
                "tags_json, mod) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    note_id,
                    model["id"],
                    deck_id,
                    json.dumps(fields),
                    json.dumps(tags or []),
                    int(time.time()),
                ),
            )
            self.db.execute(
                "INSERT INTO cards(id, note_id, deck_id, ord) " "VALUES (?, ?, ?, 0)",
                (card_id, note_id, deck_id),
            )
        return note_id

    def _used_object_ids(self) -> set:
        """Return ids in use across notes and cards.

        Notes and cards share the same millisecond-timestamp id space in
        Anki, so allocating a fresh id needs to consider both tables.
        """
        return {row["id"] for row in self.db.execute("SELECT id FROM notes")} | {
            row["id"] for row in self.db.execute("SELECT id FROM cards")
        }

    def _has_duplicate_first_field(
        self,
        deck_id: int,
        model_id: int,
        field_name: str,
        field_value: str,
    ) -> bool:
        """Check whether another note in the same deck/model has this value."""
        rows = self.db.execute(
            "SELECT fields_json FROM notes WHERE deck_id = ? AND model_id = ?",
            (deck_id, model_id),
        ).fetchall()
        for row in rows:
            existing_fields = json.loads(row["fields_json"])
            if existing_fields.get(field_name, "") == field_value:
                return True
        return False

    def all_note_rows(self) -> List[sqlite3.Row]:
        """Return all note rows joined with deck/model names.

        Returns:
            A list of joined rows ordered by note id.
        """
        return list(
            self.db.execute(
                "SELECT n.id            AS id, "
                "       n.fields_json   AS fields_json, "
                "       n.tags_json     AS tags_json, "
                "       n.mod           AS mod, "
                "       n.deck_id       AS deck_id, "
                "       d.name          AS deck_name, "
                "       n.model_id      AS model_id, "
                "       m.name          AS model_name, "
                "       m.fields_json   AS model_fields "
                "FROM notes n "
                "JOIN decks d  ON d.id = n.deck_id "
                "JOIN models m ON m.id = n.model_id "
                "ORDER BY n.id"
            ).fetchall()
        )

    def all_card_rows(self) -> List[sqlite3.Row]:
        """Return all card rows joined with deck/note metadata.

        Returns:
            A list of joined rows ordered by card id.
        """
        return list(
            self.db.execute(
                "SELECT c.id        AS id, "
                "       c.note_id   AS note_id, "
                "       c.deck_id   AS deck_id, "
                "       c.ord       AS ord, "
                "       c.queue     AS queue, "
                "       c.due       AS due, "
                "       c.ivl       AS ivl, "
                "       c.factor    AS factor, "
                "       c.reps      AS reps, "
                "       c.lapses    AS lapses, "
                "       c.flags     AS flags, "
                "       c.suspended AS suspended, "
                "       d.name      AS deck_name "
                "FROM cards c "
                "JOIN decks d ON d.id = c.deck_id "
                "ORDER BY c.id"
            ).fetchall()
        )

    def cards_for_notes(self, note_ids: Iterable[int]) -> List[int]:
        """Return card ids for the given note ids.

        Args:
            note_ids: Iterable of note ids.

        Returns:
            A list of card ids ordered by card id.
        """
        ids = list(note_ids)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        return [
            row["id"]
            for row in self.db.execute(
                f"SELECT id FROM cards WHERE note_id IN ({placeholders}) "
                "ORDER BY id",
                ids,
            )
        ]

    def update_note_fields(self, note_id: int, fields: Dict[str, str]) -> None:
        """Merge ``fields`` into an existing note's fields.

        Args:
            note_id: Target note id.
            fields: Fields to overwrite.

        Raises:
            ValueError: If no note with that id exists.
        """
        row = self.db.execute(
            "SELECT fields_json FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise ValueError("note was not found")
        merged = json.loads(row["fields_json"])
        merged.update(fields)
        with self._lock:
            self.db.execute(
                "UPDATE notes SET fields_json = ?, mod = ? WHERE id = ?",
                (json.dumps(merged), int(time.time()), note_id),
            )

    def update_note_tags(self, note_id: int, tags: List[str]) -> None:
        """Replace the tag list for a note.

        Args:
            note_id: Target note id.
            tags: New tag list (replaces existing tags).

        Raises:
            ValueError: If no note with that id exists.
        """
        row = self.db.execute("SELECT 1 FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            raise ValueError("note was not found")
        with self._lock:
            self.db.execute(
                "UPDATE notes SET tags_json = ?, mod = ? WHERE id = ?",
                (json.dumps(tags), int(time.time()), note_id),
            )

    def delete_notes(self, note_ids: Iterable[int]) -> None:
        """Delete notes (cards cascade via foreign key).

        Args:
            note_ids: Iterable of note ids to remove.
        """
        ids = list(note_ids)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            self.db.execute(f"DELETE FROM notes WHERE id IN ({placeholders})", ids)

    def change_card_deck(self, card_ids: Iterable[int], deck_name: str) -> None:
        """Move cards to a different deck (creating it if necessary).

        Args:
            card_ids: Iterable of card ids to move.
            deck_name: Destination deck name.
        """
        ids = list(card_ids)
        if not ids:
            return
        deck_id = self.get_or_create_deck(deck_name)
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            self.db.execute(
                f"UPDATE cards SET deck_id = ? WHERE id IN ({placeholders})",
                [deck_id, *ids],
            )

    def get_all_tags(self) -> List[str]:
        """Return the union of all tags across all notes.

        Returns:
            A sorted list of unique tag strings.
        """
        seen: set[str] = set()
        for row in self.db.execute("SELECT tags_json FROM notes"):
            for tag in json.loads(row["tags_json"]):
                seen.add(tag)
        return sorted(seen)

    def load_seed(self, payload: Dict[str, Any]) -> None:
        """Load decks, models, and notes from a JSON-serializable payload.

        The payload schema is::

            {
              "decks":  ["NameA", "NameB"],
              "models": [{"name": "Basic", "fields": ["Front", "Back"]}],
              "notes":  [{
                  "deckName":  "NameA",
                  "modelName": "Basic",
                  "fields":    {"Front": "...", "Back": "..."},
                  "tags":      ["t1"],
                  "cards":     [{"due": 0, "flags": 1, "ivl": 7}]
              }]
            }

        Args:
            payload: Seed dictionary as described above.
        """
        for deck_name in payload.get("decks", []):
            self.get_or_create_deck(deck_name)
        for model_spec in payload.get("models", []):
            if self.get_model(model_spec["name"]) is not None:
                continue
            used = {row["id"] for row in self.db.execute("SELECT id FROM models")}
            new_id = self.next_id(used)
            with self._lock:
                self.db.execute(
                    "INSERT INTO models(id, name, fields_json, templates_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        new_id,
                        model_spec["name"],
                        json.dumps(model_spec["fields"]),
                        json.dumps(model_spec.get("templates", [])),
                    ),
                )
        for note_spec in payload.get("notes", []):
            note_id = self.add_note(
                deck_name=note_spec["deckName"],
                model_name=note_spec["modelName"],
                fields=note_spec["fields"],
                tags=note_spec.get("tags"),
                allow_duplicate=True,
            )
            card_specs = note_spec.get("cards") or []
            if not card_specs:
                continue
            existing = list(
                self.db.execute(
                    "SELECT id FROM cards WHERE note_id = ? ORDER BY id",
                    (note_id,),
                )
            )
            for index, card_spec in enumerate(card_specs):
                if index < len(existing):
                    self._update_card(existing[index]["id"], card_spec)
                else:
                    self._insert_extra_card(note_id, index, card_spec)

    def _update_card(self, card_id: int, spec: Dict[str, Any]) -> None:
        """Patch fields on an existing card row.

        Args:
            card_id: Card primary key.
            spec: Mapping of column names to new values.
        """
        allowed = {
            "queue",
            "due",
            "ivl",
            "factor",
            "reps",
            "lapses",
            "flags",
            "suspended",
        }
        updates = {k: v for k, v in spec.items() if k in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{k} = ?" for k in updates)
        with self._lock:
            self.db.execute(
                f"UPDATE cards SET {assignments} WHERE id = ?",
                [*updates.values(), card_id],
            )

    def _insert_extra_card(
        self, note_id: int, ord_value: int, spec: Dict[str, Any]
    ) -> None:
        """Insert an additional card for a note (used by seeding only).

        Args:
            note_id: Owning note id.
            ord_value: Card template ordinal.
            spec: Card field overrides.
        """
        deck_row = self.db.execute(
            "SELECT deck_id FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        card_id = self.next_id(self._used_object_ids())
        with self._lock:
            self.db.execute(
                "INSERT INTO cards(id, note_id, deck_id, ord) " "VALUES (?, ?, ?, ?)",
                (card_id, note_id, deck_row["deck_id"], ord_value),
            )
        self._update_card(card_id, spec)
