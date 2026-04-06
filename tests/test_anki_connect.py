"""Tests for the AnkiConnect client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from anki_helpers.anki_connect import AnkiConnect, AnkiConnectError


class TestInvoke:
    """Tests for AnkiConnect._invoke."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_invoke_success(self, mock_post):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": ["Default"], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client._invoke("deckNames")

        mock_post.assert_called_once_with(
            "http://localhost:8765",
            json={"action": "deckNames", "version": 6, "params": {}},
        )
        assert result == ["Default"]

    @patch("anki_helpers.anki_connect.requests.post")
    def test_invoke_api_error(self, mock_post):
        """Test API returning an error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None, "error": "deck not found"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        with pytest.raises(AnkiConnectError, match="AnkiConnect error: deck not found"):
            client._invoke("deckNames")

    @patch("anki_helpers.anki_connect.requests.post")
    def test_invoke_network_error(self, mock_post):
        """Test network failure."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        client = AnkiConnect()
        with pytest.raises(AnkiConnectError, match="Failed to connect to AnkiConnect"):
            client._invoke("deckNames")

    @patch("anki_helpers.anki_connect.requests.post")
    def test_invoke_with_params(self, mock_post):
        """Test API call with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [1, 2, 3], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client._invoke("findNotes", query="flag:1")

        mock_post.assert_called_once_with(
            "http://localhost:8765",
            json={"action": "findNotes", "version": 6, "params": {"query": "flag:1"}},
        )
        assert result == [1, 2, 3]

    def test_custom_url(self):
        """Test custom URL initialization."""
        client = AnkiConnect(url="http://anki:9876")
        assert client.url == "http://anki:9876"


class TestGetDeckNames:
    """Tests for AnkiConnect.get_deck_names."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_get_deck_names(self, mock_post):
        """Test getting deck names."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": ["Default", "Finnish", "German"],
            "error": None,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        decks = client.get_deck_names()

        assert decks == ["Default", "Finnish", "German"]

    @patch("anki_helpers.anki_connect.requests.post")
    def test_get_deck_names_empty(self, mock_post):
        """Test empty deck list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        assert client.get_deck_names() == []


class TestFindNotesWithRedFlag:
    """Tests for AnkiConnect.find_notes_with_red_flag."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_find_notes_empty(self, mock_post):
        """Test no notes found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        assert client.find_notes_with_red_flag() == []

    @patch("anki_helpers.anki_connect.requests.post")
    def test_find_notes_with_results(self, mock_post):
        """Test finding notes with red flags."""
        side_effects = [
            # findNotes query
            {"result": [101, 102], "error": None},
            # findCards query
            {"result": [201, 202], "error": None},
            # notesInfo
            {
                "result": [
                    {"noteId": 101, "fields": {"Front": {"value": "kissa"}}},
                    {"noteId": 102, "fields": {"Front": {"value": "koira"}}},
                ],
                "error": None,
            },
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = side_effects
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client.find_notes_with_red_flag()

        assert len(result) == 2
        assert result[0]["noteId"] == 101
        assert result[1]["noteId"] == 102


class TestGetIntervals:
    """Tests for AnkiConnect.get_intervals."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_get_intervals_empty(self, mock_post):
        """Test with empty card list."""
        client = AnkiConnect()
        assert client.get_intervals([]) == {}

    @patch("anki_helpers.anki_connect.requests.post")
    def test_get_intervals(self, mock_post):
        """Test getting intervals for cards."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [5, 10], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client.get_intervals([201, 202])

        assert result == {201: 5, 202: 10}


class TestFindCardsWithRedFlag:
    """Tests for AnkiConnect.find_cards_with_red_flag."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_find_cards_empty_notes(self, mock_post):
        """Test no flagged notes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        assert client.find_cards_with_red_flag() == []

    @patch("anki_helpers.anki_connect.requests.post")
    def test_find_cards_empty_cards(self, mock_post):
        """Test notes found but no cards."""
        side_effects = [
            {"result": [101], "error": None},  # findNotes
            {"result": [], "error": None},  # findCards
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = side_effects
        mock_post.return_value = mock_response

        client = AnkiConnect()
        assert client.find_cards_with_red_flag() == []

    @patch("anki_helpers.anki_connect.requests.post")
    def test_find_cards_with_data(self, mock_post):
        """Test finding cards with full data assembly."""
        side_effects = [
            {"result": [101], "error": None},  # findNotes
            {"result": [201], "error": None},  # findCards
            {  # cardsInfo
                "result": [{"cardId": 201, "note": 101, "due": 5}],
                "error": None,
            },
            {"result": [3], "error": None},  # getIntervals
            {  # notesInfo
                "result": [
                    {
                        "noteId": 101,
                        "fields": {"Front": {"value": "kissa"}},
                        "tags": ["finnish"],
                    }
                ],
                "error": None,
            },
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = side_effects
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client.find_cards_with_red_flag()

        assert len(result) == 1
        assert result[0]["noteFields"]["Front"]["value"] == "kissa"
        assert result[0]["noteTags"] == ["finnish"]
        assert result[0]["interval"] == 3


class TestFindCardsWithRedFlagSorted:
    """Tests for AnkiConnect.find_cards_with_red_flag_sorted."""

    @patch("anki_helpers.anki_connect.requests.post")
    def test_sorted_empty(self, mock_post):
        """Test no flagged notes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [], "error": None}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AnkiConnect()
        assert client.find_cards_with_red_flag_sorted() == []

    @patch("anki_helpers.anki_connect.requests.post")
    def test_sorted_with_due_query(self, mock_post):
        """Test cards get dueQuery values from multiple API calls."""
        side_effects = [
            {"result": [101, 102], "error": None},  # findNotes flag:1
            {"result": [201, 202], "error": None},  # findCards nid:
            {  # cardsInfo
                "result": [
                    {"cardId": 201, "note": 101},
                    {"cardId": 202, "note": 102},
                ],
                "error": None,
            },
            {"result": [5, 10], "error": None},  # getIntervals
            {  # notesInfo
                "result": [
                    {"noteId": 101, "fields": {"Front": {"value": "kissa"}}, "tags": []},
                    {"noteId": 102, "fields": {"Front": {"value": "koira"}}, "tags": []},
                ],
                "error": None,
            },
            {"result": [101], "error": None},  # findNotes due<0 due>-7
            {"result": [], "error": None},  # findNotes due<-6
        ]
        # Add 30 responses for the due=0..29 loop
        for due_prop in range(30):
            side_effects.append({"result": [102] if due_prop == 3 else [], "error": None})

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = side_effects
        mock_post.return_value = mock_response

        client = AnkiConnect()
        result = client.find_cards_with_red_flag_sorted()

        assert len(result) == 2
        # Card 201 (note 101) should have dueQuery=-1 (matched due<0 due>-7)
        card_201 = next(c for c in result if c["cardId"] == 201)
        assert card_201["dueQuery"] == -1
        assert card_201["noteFields"]["Front"]["value"] == "kissa"
        # Card 202 (note 102) should have dueQuery=3 (matched due=3)
        card_202 = next(c for c in result if c["cardId"] == 202)
        assert card_202["dueQuery"] == 3
        assert card_202["noteFields"]["Front"]["value"] == "koira"
