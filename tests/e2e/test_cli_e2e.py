"""End-to-end tests: installed CLI against a stub AnkiConnect server."""

import socket
from typing import Any

import pytest

from .conftest import AnkiStub, RunCli

pytestmark = pytest.mark.e2e


def test_list_deck(anki_stub: AnkiStub, run_cli: RunCli) -> None:
    """T1: decks are listed sorted."""
    anki_stub.responses["deckNames"] = ["B", "A"]
    result = run_cli("list-deck", url=anki_stub.url)
    assert result.returncode == 0
    assert result.stdout == "Available decks:\n  • A\n  • B\n"
    assert len(anki_stub.requests) == 1
    assert anki_stub.requests[0]["action"] == "deckNames"
    assert anki_stub.requests[0]["version"] == 6


def test_list_red_flags_with_limit(anki_stub: AnkiStub, run_cli: RunCli) -> None:
    """T2: only --limit cards are printed, with HTML cleaned."""

    def find_notes(params: dict[str, Any]) -> list[int]:
        return [1, 2, 3] if params["query"] == "flag:1" else []

    anki_stub.responses.update(
        {
            "findNotes": find_notes,
            "findCards": [11, 12, 13],
            "cardsInfo": [{"cardId": 10 + n, "note": n} for n in (1, 2, 3)],
            "getIntervals": [5, 6, 7],
            "notesInfo": [
                {
                    "noteId": n,
                    "fields": {"Front": {"value": f"<b>word{n}</b>&nbsp;x"}},
                    "tags": [f"tag{n}"],
                }
                for n in (1, 2, 3)
            ],
        }
    )
    result = run_cli("list-red-flags", "--limit", "2", url=anki_stub.url)
    assert result.returncode == 0
    assert "word1 x" in result.stdout
    assert "word2 x" in result.stdout
    assert "word3" not in result.stdout
    assert "<b>" not in result.stdout


def test_list_deck_empty(anki_stub: AnkiStub, run_cli: RunCli) -> None:
    """T3: no decks prints a notice."""
    anki_stub.responses["deckNames"] = []
    result = run_cli("list-deck", url=anki_stub.url)
    assert result.returncode == 0
    assert result.stdout.strip() == "No decks found."


def test_anki_down(run_cli: RunCli) -> None:
    """T4: a closed port yields an error and a hint on stderr."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    result = run_cli("list-deck", url=f"http://127.0.0.1:{port}")
    assert result.returncode == 0
    assert "Failed to connect to AnkiConnect" in result.stderr
    assert "Make sure Anki is running" in result.stderr
