"""Data transformation for AnkiConnect API responses to SQLite rows."""

import json
from typing import Any


def transform_notes_row(
    note_info: dict[str, Any],
    card_info: dict[str, Any],
    days_elapsed: int,
) -> dict[str, Any]:
    """Transform a single note+card pair into a notes table row.

    Args:
        note_info: Response from notesInfo API.
        card_info: Response from cardsInfo API.
        days_elapsed: Days since Anki collection creation.

    Returns:
        Dict matching the notes table schema.
    """
    fields = note_info.get("fields", {})
    # Convert fields to {name: value} for compact storage
    fields_data = {name: data.get("value", "") for name, data in fields.items()}

    queue = card_info.get("queue", 0)
    raw_due = card_info.get("due", 0)

    return {
        "card_id": card_info.get("cardId"),
        "note_id": note_info.get("noteId"),
        "deck_name": card_info.get("deckName", ""),
        "fields": json.dumps(fields_data),
        "tags": json.dumps(note_info.get("tags", [])),
        "due": raw_due,
        "interval": card_info.get("interval", 0),
        "flag": card_info.get("flags", 0),
        "queue": queue,
        "due_query": convert_due_query(raw_due, queue, days_elapsed),
        "modified": note_info.get("mod", 0),
    }


def convert_due_query(raw_due: int, queue: int, days_elapsed: int) -> int:
    """Convert raw due value to relative-day due_query for sorting.

    Args:
        raw_due: Raw due value from cardsInfo.
        queue: Card queue type (0=new, 1=learning, 2=review, 3=relearning).
        days_elapsed: Days since Anki collection creation.

    Returns:
        Converted due_query value for sorting.
    """
    # Review/relearning cards: relative days from today
    if queue in (2, 3):
        return raw_due - days_elapsed
    # New cards: ordinal position (already relative)
    # Learning cards: Unix timestamp (sorts chronologically)
    return raw_due


def merge_notes_and_cards(
    notes_info: list[dict[str, Any]],
    cards_info: list[dict[str, Any]],
    days_elapsed: int,
) -> list[dict[str, Any]]:
    """Merge notesInfo and cardsInfo data into notes table rows.

    Joins by note_id -> card_id mapping from notesInfo.cards field.

    Args:
        notes_info: List of notesInfo API responses.
        cards_info: List of cardsInfo API responses.
        days_elapsed: Days since Anki collection creation.

    Returns:
        List of dicts matching the notes table schema.
    """
    notes_by_id: dict[int, dict[str, Any]] = {note["noteId"]: note for note in notes_info}
    rows = []
    for card in cards_info:
        note_id = card.get("note")
        if note_id is None or note_id not in notes_by_id:
            continue
        note = notes_by_id[note_id]
        rows.append(transform_notes_row(note, card, days_elapsed))
    return rows
