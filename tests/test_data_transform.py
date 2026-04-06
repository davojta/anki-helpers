"""Unit tests for data transformation module."""

import json

from anki_helpers.data_transform import (
    convert_due_query,
    merge_notes_and_cards,
    transform_notes_row,
)


def _make_note_info(note_id=100, fields=None, tags=None, mod=1000000, cards=None):
    """Create a mock notesInfo response."""
    if fields is None:
        fields = {"Front": {"value": "hello"}, "Back": {"value": "world"}}
    if tags is None:
        tags = ["tag1"]
    if cards is None:
        cards = [1, 2]
    return {
        "noteId": note_id,
        "fields": fields,
        "tags": tags,
        "mod": mod,
        "cards": cards,
    }


def _make_card_info(
    card_id=1, note_id=100, deck_name="Default", due=5, interval=10, flags=0, queue=2
):
    """Create a mock cardsInfo response."""
    return {
        "cardId": card_id,
        "note": note_id,
        "deckName": deck_name,
        "due": due,
        "interval": interval,
        "flags": flags,
        "queue": queue,
    }


class TestTransformNotesRow:
    def test_extracts_fields(self):
        note = _make_note_info(note_id=100)
        card = _make_card_info(card_id=1, note_id=100)
        row = transform_notes_row(note, card, days_elapsed=100)

        assert row["card_id"] == 1
        assert row["note_id"] == 100
        assert row["deck_name"] == "Default"
        assert json.loads(row["fields"]) == {"Front": "hello", "Back": "world"}
        assert json.loads(row["tags"]) == ["tag1"]
        assert row["flag"] == 0
        assert row["queue"] == 2
        assert row["modified"] == 1000000

    def test_flag_from_cards_info_flags(self):
        note = _make_note_info()
        card = _make_card_info(flags=1)
        row = transform_notes_row(note, card, days_elapsed=0)
        assert row["flag"] == 1


class TestConvertDueQuery:
    def test_review_cards(self):
        # queue=2 (review): due_query = raw_due - days_elapsed
        assert convert_due_query(105, 2, 100) == 5
        assert convert_due_query(95, 2, 100) == -5  # overdue

    def test_relearning_cards(self):
        # queue=3 (relearning): same as review
        assert convert_due_query(110, 3, 100) == 10

    def test_new_cards(self):
        # queue=0: due_query = raw_due (ordinal)
        assert convert_due_query(42, 0, 100) == 42

    def test_learning_cards(self):
        # queue=1: due_query = raw_due (timestamp)
        assert convert_due_query(1700000000, 1, 100) == 1700000000


class TestMergeNotesAndCards:
    def test_basic_merge(self):
        notes = [_make_note_info(note_id=100, cards=[1, 2])]
        cards = [
            _make_card_info(card_id=1, note_id=100),
            _make_card_info(card_id=2, note_id=100),
        ]
        rows = merge_notes_and_cards(notes, cards, days_elapsed=100)
        assert len(rows) == 2
        assert rows[0]["card_id"] == 1
        assert rows[1]["card_id"] == 2

    def test_skips_cards_without_note(self):
        notes = [_make_note_info(note_id=100)]
        cards = [
            _make_card_info(card_id=1, note_id=100),
            _make_card_info(card_id=2, note_id=999),  # orphan card
        ]
        rows = merge_notes_and_cards(notes, cards, days_elapsed=100)
        assert len(rows) == 1

    def test_due_query_conversion_applied(self):
        notes = [_make_note_info(note_id=100, cards=[1])]
        cards = [_make_card_info(card_id=1, note_id=100, due=105, queue=2)]
        rows = merge_notes_and_cards(notes, cards, days_elapsed=100)
        assert rows[0]["due_query"] == 5
