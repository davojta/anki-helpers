"""AnkiConnect API client for Anki Helpers."""

from typing import Any

import requests


class AnkiConnectError(Exception):
    """Base exception for AnkiConnect related errors."""

    pass


class AnkiConnect:
    """Client for interacting with AnkiConnect API."""

    def __init__(self, url: str = "http://localhost:8765"):
        """Initialize AnkiConnect client.

        Args:
            url: The URL where AnkiConnect is running.
                Defaults to localhost:8765.
        """
        self.url = url

    def _invoke(self, action: str, **params) -> Any:
        """Invoke an AnkiConnect action.

        Args:
            action: The AnkiConnect action to invoke.
            **params: Additional parameters for the action.

        Returns:
            The response from AnkiConnect.

        Raises:
            AnkiConnectError: If the request fails or returns
                an error.
        """
        try:
            response = requests.post(
                self.url, json={"action": action, "version": 6, "params": params}
            )
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                msg = f"AnkiConnect error: {result['error']}"
                raise AnkiConnectError(msg) from None

            return result.get("result")
        except requests.RequestException as e:
            msg = f"Failed to connect to AnkiConnect: {str(e)}"
            raise AnkiConnectError(msg) from e

    def get_deck_names(self) -> list[str]:
        """Get a list of all deck names.

        Returns:
            A list of deck names.
        """
        return self._invoke("deckNames")

    def find_notes_with_red_flag(self) -> list[dict[str, Any]]:
        """Find all notes that have a red flag.

        In Anki, red flags are typically marked with the tag 'marked'.

        Returns:
            A list of cards with red flags, including their content, due date, and dueQuery field.
            The dueQuery field indicates if the card is due (0) or not (-1).
        """
        # First, find all note IDs with red flags
        query = "flag:1"
        note_ids = self._invoke("findNotes", query=query)

        if not note_ids:
            return []

        # Find all card IDs for these notes
        card_ids = self._invoke("findCards", query=f"nid:{','.join(map(str, note_ids))}")

        if not card_ids:
            return []

        # Get note info to include content
        notes_info = self._invoke("notesInfo", notes=note_ids)

        return notes_info

    def get_intervals(self, card_ids: list[int]) -> dict[int, int]:
        """Get intervals for the specified cards.

        Args:
            card_ids: List of card IDs to get intervals for.

        Returns:
            A dictionary mapping card IDs to their intervals.
        """
        if not card_ids:
            return {}

        intervals = self._invoke("getIntervals", cards=card_ids)

        # Create a dictionary mapping card IDs to their intervals
        return {card_id: interval for card_id, interval in zip(card_ids, intervals, strict=False)}

    def find_cards_with_red_flag(self) -> list[dict[str, Any]]:
        """Find all cards that have a red flag and include due date information.

        Returns:
            A list of cards with red flags, including their content and due date.
        """
        # First, find all note IDs with red flags
        query = "flag:1"
        note_ids = self._invoke("findNotes", query=query)

        if not note_ids:
            return []

        # Find all card IDs for these notes
        card_ids = self._invoke("findCards", query=f"nid:{','.join(map(str, note_ids))}")

        if not card_ids:
            return []

        # Get card info including due date
        cards_info = self._invoke("cardsInfo", cards=card_ids)

        # Get intervals for these cards
        intervals = self.get_intervals(card_ids)

        # Get note info to include content
        notes_info = self._invoke("notesInfo", notes=note_ids)

        # Create a dictionary to quickly look up notes by ID
        notes_by_id = {note["noteId"]: note for note in notes_info}

        # Combine card info with note content and intervals
        for card in cards_info:
            note_id = card.get("note")
            card_id = card.get("cardId")
            if note_id in notes_by_id:
                card["noteFields"] = notes_by_id[note_id].get("fields", {})
                card["noteTags"] = notes_by_id[note_id].get("tags", [])
            if card_id in intervals:
                card["interval"] = intervals[card_id]

        return cards_info

    def get_all_notes_info(self) -> list[dict[str, Any]]:
        """Get info for all notes in the collection.

        Returns:
            List of note info dicts with fields, tags, mod, cards list.
        """
        return self._invoke("notesInfo", query="")

    def get_cards_info(self, card_ids: list[int]) -> list[dict[str, Any]]:
        """Get info for specific cards.

        Args:
            card_ids: List of card IDs.

        Returns:
            List of card info dicts with deck, due, interval, flags, queue.
        """
        if not card_ids:
            return []
        return self._invoke("cardsInfo", cards=card_ids)

    def find_edited_notes(self, days: int) -> list[int]:
        """Find notes edited within the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            List of note IDs.
        """
        return self._invoke("findNotes", query=f"edited:{days}")

    def find_notes_info(self, note_ids: list[int]) -> list[dict[str, Any]]:
        """Get info for specific notes by their IDs.

        Args:
            note_ids: List of note IDs.

        Returns:
            List of note info dicts.
        """
        if not note_ids:
            return []
        return self._invoke("notesInfo", notes=note_ids)

    def find_cards(self, query: str) -> list[int]:
        """Find card IDs matching a search query.

        Args:
            query: Anki search query string.

        Returns:
            List of card IDs.
        """
        return self._invoke("findCards", query=query)

    def get_days_elapsed(self) -> int:
        """Determine days elapsed since Anki collection creation.

        Uses findCards("prop:due=0") and reads raw due from a returned card.

        Returns:
            The days_elapsed value from Anki.
        """
        card_ids = self._invoke("findCards", query="prop:due=0")
        if not card_ids:
            return 0
        cards_info = self._invoke("cardsInfo", cards=[card_ids[0]])
        if cards_info:
            return cards_info[0].get("due", 0)
        return 0

    def find_cards_with_red_flag_sorted(self) -> list[dict[str, Any]]:
        """Find all cards that have a red flag and include due date information with sorting.

        Returns:
            A list of cards with red flags, including their content, due date, and dueQuery field.
            The dueQuery field indicates if the card is due (0) or not (-1).
        """
        # First, find all note IDs with red flags
        query = "flag:1"
        note_ids = self._invoke("findNotes", query=query)

        if not note_ids:
            return []

        # Find all card IDs for these notes
        card_ids = self._invoke("findCards", query=f"nid:{','.join(map(str, note_ids))}")

        if not card_ids:
            return []

        # Get card info including due date
        cards_info = self._invoke("cardsInfo", cards=card_ids)

        # Get intervals for these cards
        intervals = self.get_intervals(card_ids)

        # Get note info to include content
        notes_info = self._invoke("notesInfo", notes=note_ids)

        # Create dictionaries to quickly look up notes by ID
        notes_by_id = {note["noteId"]: note for note in notes_info}

        # Default dueQuery value for all notes
        for note in notes_info:
            note["dueQuery"] = 90

        query = "flag:1 prop:due<0 prop:due>-7"
        due_note_ids = self._invoke("findNotes", query=query)

        # Update dueQuery for due notes
        for note in notes_info:
            if note["noteId"] in due_note_ids:
                note["dueQuery"] = -1
        query = "flag:1 prop:due<-6"
        due_note_ids = self._invoke("findNotes", query=query)

        # Update dueQuery for due notes
        for note in notes_info:
            if note["noteId"] in due_note_ids:
                note["dueQuery"] = -2

        # Find all due notes with flag:1 for due days 0-14
        for dueProp in range(30):  # 0 to 14
            query = f"flag:1 prop:due={dueProp}"
            due_note_ids = self._invoke("findNotes", query=query)

            # Update dueQuery for due notes
            for note in notes_info:
                if note["noteId"] in due_note_ids:
                    note["dueQuery"] = dueProp

        # Combine card info with note content, intervals, and dueQuery
        for card in cards_info:
            note_id = card.get("note")
            card_id = card.get("cardId")
            if note_id in notes_by_id:
                card["noteFields"] = notes_by_id[note_id].get("fields", {})
                card["noteTags"] = notes_by_id[note_id].get("tags", [])
                # Add the dueQuery from the note to the card
                card["dueQuery"] = notes_by_id[note_id].get("dueQuery", -1)
            if card_id in intervals:
                card["interval"] = intervals[card_id]

        return cards_info
