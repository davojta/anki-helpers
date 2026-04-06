"""Unit tests for SQLiteStorage."""

import sqlite3
from datetime import UTC, datetime

import pytest

from anki_helpers.sqlite_storage import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    """Create an in-memory SQLiteStorage for testing."""
    db_path = tmp_path / "test.db"
    s = SQLiteStorage(db_path)
    with s:
        yield s


def _make_note(card_id=1, note_id=100, deck_name="Default", flag=0, due_query=0, **kwargs):
    """Helper to create a note dict for testing."""
    import json

    return {
        "card_id": card_id,
        "note_id": note_id,
        "deck_name": deck_name,
        "fields": json.dumps({"Front": "test", "Back": "value"}),
        "tags": json.dumps(["tag1"]),
        "due": kwargs.get("due", 0),
        "interval": kwargs.get("interval", 0),
        "flag": flag,
        "queue": kwargs.get("queue", 2),
        "due_query": due_query,
        "modified": kwargs.get("modified", 1000000),
    }


class TestInit:
    def test_creates_database(self, tmp_path):
        db_path = tmp_path / "new.db"
        assert not db_path.exists()
        with SQLiteStorage(db_path):
            assert db_path.exists()

    def test_schema_created(self, storage):
        # notes table exists
        result = storage.execute_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notes'"
        )
        assert len(result) == 1
        # sync_log table exists
        result = storage.execute_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_log'"
        )
        assert len(result) == 1


class TestReplaceAll:
    def test_inserts_notes(self, storage):
        notes = [_make_note(card_id=1), _make_note(card_id=2)]
        storage.replace_all(notes)
        assert storage.get_total_cards() == 2

    def test_replaces_existing(self, storage):
        storage.replace_all([_make_note(card_id=1), _make_note(card_id=2)])
        storage.replace_all([_make_note(card_id=3)])
        assert storage.get_total_cards() == 1

    def test_empty_clears_all(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        storage.replace_all([])
        assert storage.get_total_cards() == 0

    def test_atomic_on_failure(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        bad_note = {"card_id": 2}
        with pytest.raises(sqlite3.Error):
            storage.replace_all([bad_note])
        assert storage.get_total_cards() == 1


class TestUpsertNotes:
    def test_all_new(self, storage):
        notes = [_make_note(card_id=1), _make_note(card_id=2)]
        new, updated = storage.upsert_notes(notes)
        assert new == 2
        assert updated == 0

    def test_all_existing(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        new, updated = storage.upsert_notes([_make_note(card_id=1)])
        assert new == 0
        assert updated == 1

    def test_mixed(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        notes = [_make_note(card_id=1), _make_note(card_id=2)]
        new, updated = storage.upsert_notes(notes)
        assert new == 1
        assert updated == 1

    def test_empty_input(self, storage):
        new, updated = storage.upsert_notes([])
        assert new == 0
        assert updated == 0

    def test_atomic_on_failure(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        bad_note = {"card_id": 2}
        with pytest.raises(sqlite3.Error):
            storage.upsert_notes([_make_note(card_id=3), bad_note])
        assert storage.get_total_cards() == 1


class TestSyncLog:
    def test_add_and_get(self, storage):
        storage.add_sync_log(total_cards=150, deck_count=5, new_cards=12, updated_cards=8)
        result = storage.get_last_sync()
        assert result is not None
        assert result["total_cards"] == 150
        assert result["deck_count"] == 5
        assert result["new_cards"] == 12
        assert result["updated_cards"] == 8

    def test_iso_timestamp_format(self, storage):
        storage.add_sync_log(total_cards=0, deck_count=0, new_cards=0, updated_cards=0)
        result = storage.get_last_sync()
        # Should be valid ISO format
        dt = datetime.fromisoformat(result["synced_at"])
        assert dt.tzinfo is not None

    def test_epoch_is_reasonable(self, storage):
        storage.add_sync_log(total_cards=0, deck_count=0, new_cards=0, updated_cards=0)
        result = storage.get_last_sync()
        now = datetime.now(tz=UTC)
        assert abs(now.timestamp() - result["synced_at_epoch"]) < 5

    def test_no_sync_returns_none(self, storage):
        assert storage.get_last_sync() is None

    def test_returns_most_recent(self, storage):
        storage.add_sync_log(total_cards=10, deck_count=1, new_cards=10, updated_cards=0)
        storage.add_sync_log(total_cards=20, deck_count=2, new_cards=10, updated_cards=0)
        result = storage.get_last_sync()
        assert result["total_cards"] == 20


class TestQueries:
    def test_get_cards_by_flag(self, storage):
        storage.replace_all(
            [
                _make_note(card_id=1, flag=1),
                _make_note(card_id=2, flag=0),
                _make_note(card_id=3, flag=1, due_query=5),
            ]
        )
        result = storage.get_cards_by_flag(1)
        assert len(result) == 2
        # Sorted by due_query ascending
        assert result[0]["due_query"] <= result[1]["due_query"]

    def test_get_cards_by_flag_empty(self, storage):
        assert storage.get_cards_by_flag(1) == []

    def test_get_deck_names(self, storage):
        storage.replace_all(
            [
                _make_note(card_id=1, deck_name="Deck B"),
                _make_note(card_id=2, deck_name="Deck A"),
                _make_note(card_id=3, deck_name="Deck A"),
            ]
        )
        decks = storage.get_deck_names()
        assert decks == ["Deck A", "Deck B"]

    def test_get_total_cards(self, storage):
        storage.replace_all([_make_note(card_id=1), _make_note(card_id=2)])
        assert storage.get_total_cards() == 2

    def test_get_note_by_card_id(self, storage):
        storage.replace_all([_make_note(card_id=42, note_id=100)])
        result = storage.get_note_by_card_id(42)
        assert result is not None
        assert result["note_id"] == 100

    def test_get_note_by_card_id_not_found(self, storage):
        assert storage.get_note_by_card_id(999) is None


class TestExecuteSql:
    def test_valid_select(self, storage):
        storage.replace_all([_make_note(card_id=1)])
        result = storage.execute_sql("SELECT COUNT(*) as cnt FROM notes")
        assert result == [{"cnt": 1}]

    def test_non_select_rejected(self, storage):
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            storage.execute_sql("DELETE FROM notes")

    def test_drop_rejected(self, storage):
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            storage.execute_sql("DROP TABLE notes")

    def test_insert_rejected(self, storage):
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            storage.execute_sql("INSERT INTO notes (card_id) VALUES (1)")

    def test_update_rejected(self, storage):
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            storage.execute_sql("UPDATE notes SET flag=1")
