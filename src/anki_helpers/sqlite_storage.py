"""SQLite storage layer for cached Anki data."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SQLiteStorage:
    """SQLite database for caching Anki card/note data."""

    def __init__(self, db_path: str | Path = ".anki-cache.db"):
        """Initialize SQLite storage.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = str(db_path)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        """Open database connection and ensure schema exists."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_schema(self):
        """Create database tables if they don't exist."""
        assert self.conn is not None
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                card_id INTEGER PRIMARY KEY,
                note_id INTEGER NOT NULL,
                deck_name TEXT NOT NULL,
                fields TEXT NOT NULL,
                tags TEXT NOT NULL,
                due INTEGER NOT NULL,
                interval INTEGER NOT NULL,
                flag INTEGER NOT NULL DEFAULT 0,
                queue INTEGER NOT NULL DEFAULT 0,
                due_query INTEGER NOT NULL DEFAULT 0,
                modified INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                synced_at TEXT NOT NULL,
                synced_at_epoch INTEGER NOT NULL,
                total_cards INTEGER NOT NULL DEFAULT 0,
                deck_count INTEGER NOT NULL DEFAULT 0,
                new_cards INTEGER NOT NULL DEFAULT 0,
                updated_cards INTEGER NOT NULL DEFAULT 0
            );
        """)

    def replace_all(self, notes: list[dict[str, Any]]) -> None:
        """Replace all cached notes atomically.

        Used for initial sync only. Deletes all existing rows and inserts
        new ones in a single transaction.

        Args:
            notes: List of note dicts with keys matching notes table columns.
        """
        assert self.conn is not None
        with self.conn:
            self.conn.execute("DELETE FROM notes")
            if notes:
                self.conn.executemany(
                    """INSERT INTO notes
                       (card_id, note_id, deck_name, fields, tags, due, interval,
                        flag, queue, due_query, modified)
                       VALUES (:card_id, :note_id, :deck_name, :fields, :tags,
                               :due, :interval, :flag, :queue, :due_query, :modified)""",
                    notes,
                )

    def upsert_notes(self, notes: list[dict[str, Any]]) -> tuple[int, int]:
        """Upsert notes by card_id. Returns (new_count, updated_count).

        Args:
            notes: List of note dicts to insert or update.

        Returns:
            Tuple of (newly inserted count, updated existing count).
        """
        if not notes:
            return (0, 0)

        assert self.conn is not None
        new_count = 0
        updated_count = 0

        with self.conn:
            for note in notes:
                card_id = note["card_id"]
                existing = self.conn.execute(
                    "SELECT 1 FROM notes WHERE card_id = ?", (card_id,)
                ).fetchone()
                self.conn.execute(
                    """INSERT OR REPLACE INTO notes
                       (card_id, note_id, deck_name, fields, tags, due, interval,
                        flag, queue, due_query, modified)
                       VALUES (:card_id, :note_id, :deck_name, :fields, :tags,
                               :due, :interval, :flag, :queue, :due_query, :modified)""",
                    note,
                )
                if existing:
                    updated_count += 1
                else:
                    new_count += 1

        return (new_count, updated_count)

    def add_sync_log(
        self,
        total_cards: int,
        deck_count: int,
        new_cards: int,
        updated_cards: int,
    ) -> None:
        """Record a sync log entry with current UTC timestamp.

        Args:
            total_cards: Total cards in cache after sync.
            deck_count: Number of distinct decks.
            new_cards: Number of newly inserted cards.
            updated_cards: Number of updated existing cards.
        """
        assert self.conn is not None
        now = datetime.now(tz=UTC)
        self.conn.execute(
            """INSERT INTO sync_log
               (synced_at, synced_at_epoch, total_cards, deck_count, new_cards, updated_cards)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                now.isoformat(),
                int(now.timestamp()),
                total_cards,
                deck_count,
                new_cards,
                updated_cards,
            ),
        )
        self.conn.commit()

    def get_cards_by_flag(self, flag: int) -> list[dict[str, Any]]:
        """Query notes filtered by flag value, sorted by due_query ascending.

        Args:
            flag: Flag value to filter by (0-7).

        Returns:
            List of note dicts matching the flag.
        """
        assert self.conn is not None
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE flag = ? ORDER BY due_query ASC", (flag,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_deck_names(self) -> list[str]:
        """Get distinct deck names, sorted.

        Returns:
            Sorted list of unique deck names.
        """
        assert self.conn is not None
        rows = self.conn.execute(
            "SELECT DISTINCT deck_name FROM notes ORDER BY deck_name"
        ).fetchall()
        return [row["deck_name"] for row in rows]

    def get_last_sync(self) -> dict[str, Any] | None:
        """Get the most recent sync log entry.

        Returns:
            Dict with sync log fields, or None if no sync has occurred.
        """
        assert self.conn is not None
        row = self.conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_total_cards(self) -> int:
        """Get total number of cards in notes table.

        Returns:
            Count of rows in notes table.
        """
        assert self.conn is not None
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM notes").fetchone()
        return row["cnt"]

    def get_note_by_card_id(self, card_id: int) -> dict[str, Any] | None:
        """Get a single note by card_id.

        Args:
            card_id: The Anki card ID to look up.

        Returns:
            Note dict or None if not found.
        """
        assert self.conn is not None
        row = self.conn.execute("SELECT * FROM notes WHERE card_id = ?", (card_id,)).fetchone()
        return dict(row) if row else None

    def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query.

        Args:
            sql: SQL query string. Only SELECT statements are allowed.

        Returns:
            List of dicts representing result rows.

        Raises:
            ValueError: If the SQL is not a SELECT statement.
        """
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT"):
            msg = "Only SELECT queries are allowed"
            raise ValueError(msg)

        assert self.conn is not None
        cursor = self.conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
