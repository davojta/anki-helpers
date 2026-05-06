"""Tests for the AnkiConnect mock server."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from anki_helpers.mock_server.server import MockAnkiConnectServer  # noqa: E402
from anki_helpers.mock_server.state import State  # noqa: E402


def make_client() -> TestClient:
    """Build a fresh in-memory mock server wrapped in a TestClient."""
    server = MockAnkiConnectServer(State(":memory:"))
    return TestClient(server.app)


def call(client: TestClient, action: str, **params):
    """POST an AnkiConnect envelope and return the parsed JSON body."""
    response = client.post("/", json={"action": action, "version": 6, "params": params})
    assert response.status_code == 200
    return response.json()


def test_liveness_returns_anki_connect_banner():
    """GET / should mimic AnkiConnect's plain-text liveness response."""
    client = make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "AnkiConnect" in response.text


def test_version_returns_six():
    """The mock claims AnkiConnect API version 6."""
    client = make_client()
    body = call(client, "version")
    assert body == {"result": 6, "error": None}


def test_unsupported_action_returns_envelope_error():
    """Unknown actions return a populated 'error' string and null result."""
    client = make_client()
    body = call(client, "definitelyNotAnAction")
    assert body == {"result": None, "error": "unsupported action"}


def test_default_deck_is_present():
    """A fresh state exposes the seeded Default deck."""
    client = make_client()
    body = call(client, "deckNames")
    assert body["result"] == ["Default"]
    assert body["error"] is None


def test_create_deck_is_idempotent():
    """Repeat calls to createDeck for the same name reuse the existing id."""
    client = make_client()
    first = call(client, "createDeck", deck="Finnish")["result"]
    second = call(client, "createDeck", deck="Finnish")["result"]
    assert first == second
    assert "Finnish" in call(client, "deckNames")["result"]


def test_add_note_round_trips_through_notes_info():
    """An addNote followed by notesInfo returns the inserted fields and tags."""
    client = make_client()
    note_id = call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "hello", "Back": "world"},
            "tags": ["greeting"],
        },
    )["result"]
    assert isinstance(note_id, int)
    info = call(client, "notesInfo", notes=[note_id])["result"]
    assert len(info) == 1
    assert info[0]["fields"]["Front"]["value"] == "hello"
    assert info[0]["fields"]["Back"]["value"] == "world"
    assert info[0]["tags"] == ["greeting"]
    assert info[0]["modelName"] == "Basic"
    assert len(info[0]["cards"]) == 1


def test_duplicate_first_field_returns_anki_connect_error_string():
    """Duplicate notes surface the canonical AnkiConnect duplicate message."""
    client = make_client()
    payload = {
        "deckName": "Default",
        "modelName": "Basic",
        "fields": {"Front": "dup", "Back": "x"},
    }
    first = call(client, "addNote", note=payload)
    assert first["error"] is None
    second = call(client, "addNote", note=payload)
    assert second["result"] is None
    assert second["error"] == "cannot create note because it is a duplicate"


def test_can_add_notes_reports_duplicate_as_false():
    """Calls to canAddNotes return False for duplicates and True for new notes."""
    client = make_client()
    call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "exists", "Back": "x"},
        },
    )
    body = call(
        client,
        "canAddNotes",
        notes=[
            {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "exists", "Back": "x"},
            },
            {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "fresh", "Back": "x"},
            },
        ],
    )
    assert body["result"] == [False, True]


def test_find_notes_supports_flag_and_due_predicates():
    """flag:1 and prop:due predicates filter on the seeded card metadata."""
    client = make_client()
    seed = {
        "decks": ["Finnish"],
        "notes": [
            {
                "deckName": "Finnish",
                "modelName": "Basic",
                "fields": {"Front": "kissa", "Back": "cat"},
                "tags": ["marked"],
                "cards": [{"flags": 1, "due": -3, "ivl": 14, "reps": 5}],
            },
            {
                "deckName": "Finnish",
                "modelName": "Basic",
                "fields": {"Front": "talo", "Back": "house"},
                "tags": [],
                "cards": [{"flags": 0, "due": 5, "ivl": 21, "reps": 8}],
            },
        ],
    }
    response = client.post("/admin/seed", json=seed)
    assert response.status_code == 200
    flagged = call(client, "findNotes", query="flag:1")["result"]
    assert len(flagged) == 1
    overdue = call(client, "findNotes", query="flag:1 prop:due<0")["result"]
    assert overdue == flagged
    not_due_yet = call(client, "findNotes", query="flag:1 prop:due>0")["result"]
    assert not_due_yet == []


def test_find_notes_supports_deck_and_tag_with_subdecks():
    """deck:Foo matches subdecks Foo::Bar and tag:foo matches foo::sub."""
    client = make_client()
    client.post(
        "/admin/seed",
        json={
            "decks": ["Lang::FI", "Lang::EN"],
            "notes": [
                {
                    "deckName": "Lang::FI",
                    "modelName": "Basic",
                    "fields": {"Front": "kissa", "Back": "cat"},
                    "tags": ["topic::animals"],
                },
                {
                    "deckName": "Lang::EN",
                    "modelName": "Basic",
                    "fields": {"Front": "cat", "Back": "kissa"},
                    "tags": ["topic::buildings"],
                },
            ],
        },
    )
    parent = call(client, "findNotes", query="deck:Lang")["result"]
    assert len(parent) == 2
    only_fi = call(client, "findNotes", query="deck:Lang::FI")["result"]
    assert len(only_fi) == 1
    by_tag = call(client, "findNotes", query="tag:topic")["result"]
    assert len(by_tag) == 2
    only_animals = call(client, "findNotes", query="tag:topic::animals")["result"]
    assert len(only_animals) == 1


def test_find_cards_with_nid_filter_returns_owned_cards():
    """A findCards query with nid:N1,N2 returns the cards for those notes only."""
    client = make_client()
    n1 = call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "a", "Back": "1"},
        },
    )["result"]
    n2 = call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "b", "Back": "2"},
        },
    )["result"]
    cards = call(client, "findCards", query=f"nid:{n1},{n2}")["result"]
    assert len(cards) == 2


def test_get_intervals_preserves_order():
    """Calls to getIntervals return ivl values in the order requested."""
    client = make_client()
    client.post(
        "/admin/seed",
        json={
            "notes": [
                {
                    "deckName": "Default",
                    "modelName": "Basic",
                    "fields": {"Front": "x", "Back": "1"},
                    "cards": [{"ivl": 7}],
                },
                {
                    "deckName": "Default",
                    "modelName": "Basic",
                    "fields": {"Front": "y", "Back": "2"},
                    "cards": [{"ivl": 21}],
                },
            ]
        },
    )
    cards = call(client, "findCards", query="deck:Default")["result"]
    intervals = call(client, "getIntervals", cards=cards)["result"]
    assert intervals == [7, 21]


def test_update_note_fields_merges_values():
    """A call to updateNoteFields overwrites only the supplied fields."""
    client = make_client()
    note_id = call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "old", "Back": "kept"},
        },
    )["result"]
    call(
        client,
        "updateNoteFields",
        note={"id": note_id, "fields": {"Front": "new"}},
    )
    info = call(client, "notesInfo", notes=[note_id])["result"][0]
    assert info["fields"]["Front"]["value"] == "new"
    assert info["fields"]["Back"]["value"] == "kept"


def test_delete_notes_removes_cards_too():
    """A call to deleteNotes cascades to the associated cards."""
    client = make_client()
    note_id = call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "doomed", "Back": "x"},
        },
    )["result"]
    cards = call(client, "findCards", query=f"nid:{note_id}")["result"]
    assert cards
    call(client, "deleteNotes", notes=[note_id])
    after = call(client, "findCards", query=f"nid:{note_id}")["result"]
    assert after == []


def test_multi_returns_per_action_envelopes():
    """The multi action runs each sub-action and returns nested envelopes."""
    client = make_client()
    body = call(
        client,
        "multi",
        actions=[
            {"action": "version"},
            {"action": "deckNames"},
            {"action": "doesNotExist"},
        ],
    )
    assert body["error"] is None
    assert body["result"][0] == {"result": 6, "error": None}
    assert body["result"][1]["error"] is None
    assert body["result"][1]["result"] == ["Default"]
    assert body["result"][2] == {
        "result": None,
        "error": "unsupported action",
    }


def test_admin_reset_returns_to_clean_state():
    """/admin/reset removes user data while preserving Default and Basic."""
    client = make_client()
    call(
        client,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "tmp", "Back": "x"},
        },
    )
    response = client.post("/admin/reset")
    assert response.status_code == 200
    assert call(client, "findNotes", query="deck:Default")["result"] == []
    assert call(client, "deckNames")["result"] == ["Default"]
    assert call(client, "modelNames")["result"] == ["Basic"]


def test_anki_connect_client_against_mock(monkeypatch):
    """The project's AnkiConnect client should work end-to-end against the mock."""
    from anki_helpers.anki_connect import AnkiConnect

    server = MockAnkiConnectServer(State(":memory:"))
    test_client = TestClient(server.app)
    server.state.load_seed(
        {
            "decks": ["Finnish"],
            "notes": [
                {
                    "deckName": "Finnish",
                    "modelName": "Basic",
                    "fields": {"Front": "kissa", "Back": "cat"},
                    "tags": ["marked"],
                    "cards": [{"flags": 1, "due": -3, "ivl": 14, "reps": 5}],
                },
                {
                    "deckName": "Finnish",
                    "modelName": "Basic",
                    "fields": {"Front": "talo", "Back": "house"},
                    "tags": [],
                    "cards": [{"flags": 0, "due": 5, "ivl": 21, "reps": 8}],
                },
            ],
        }
    )

    def fake_post(url, json, *args, **kwargs):
        """Replace requests.post with a forward to the FastAPI TestClient."""
        del url, args, kwargs
        return test_client.post("/", json=json)

    monkeypatch.setattr("anki_helpers.anki_connect.requests.post", fake_post)

    anki = AnkiConnect()
    assert "Finnish" in anki.get_deck_names()
    cards = anki.find_cards_with_red_flag_sorted()
    assert len(cards) == 1
    front = cards[0]["noteFields"]["Front"]["value"]
    assert front == "kissa"
    assert cards[0]["interval"] == 14
