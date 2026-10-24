"""The legacy ``AnkiConnect`` client against the fake over real HTTP."""

from collections.abc import Iterator

import pytest

from anki_helpers.anki_connect import AnkiConnect, AnkiConnectError
from anki_helpers.fake_anki import FakeServer, Fault, running, sample_seed


@pytest.fixture
def fake() -> Iterator[FakeServer]:
    """Sample collection on a random port."""
    with running(sample_seed()) as server:
        yield server


@pytest.fixture
def client(fake: FakeServer) -> AnkiConnect:
    """Legacy client pointed at the fake."""
    return AnkiConnect(url=fake.url)


def test_deck_names(client: AnkiConnect) -> None:
    """The deck list includes parent decks created implicitly."""
    assert client.get_deck_names() == [
        "Default",
        "German",
        "German::Vocab",
        "Spanish",
    ]


def test_find_notes_with_red_flag(client: AnkiConnect) -> None:
    """A note is red-flagged if any of its cards has flag 1."""
    notes = client.find_notes_with_red_flag()
    assert [n["noteId"] for n in notes] == [1001, 1002, 1003, 1004, 1007]


def test_find_cards_with_red_flag(client: AnkiConnect) -> None:
    """All cards of red-flagged notes come back with fields and intervals."""
    cards = client.find_cards_with_red_flag()
    assert [c["cardId"] for c in cards] == [2001, 2002, 2003, 2004, 2005, 2008, 2009]
    assert cards[0]["noteFields"]["Front"]["value"] == "<b>der Hund</b>"
    assert cards[0]["noteTags"] == ["noun", "animals"]
    assert cards[0]["interval"] == 12


def test_find_cards_with_red_flag_sorted_due_buckets(client: AnkiConnect) -> None:
    """The dueQuery value comes from the client's prop:due queries, evaluated per card.

    Note 1004 has a flag-1 card due in 14 days and a flag-2 card 10 days
    overdue; ``flag:1 prop:due<-6`` needs both on one card, so it stays 14.
    """
    cards = client.find_cards_with_red_flag_sorted()
    assert {c["cardId"]: c["dueQuery"] for c in cards} == {
        2001: -1,
        2002: 0,
        2003: 5,
        2004: 14,
        2005: 14,
        2008: 1,
        2009: 1,
    }


def test_no_red_flags(fake: FakeServer, client: AnkiConnect) -> None:
    """An empty collection yields no cards and no notes."""
    fake.reset({})
    assert client.find_cards_with_red_flag_sorted() == []
    assert client.find_cards_with_red_flag() == []
    assert client.find_notes_with_red_flag() == []
    assert client.get_intervals([]) == {}


def test_injected_error_raises(fake: FakeServer, client: AnkiConnect) -> None:
    """An error envelope becomes AnkiConnectError."""
    fake.anki.faults.append(Fault(action="*", error="collection is not available"))
    with pytest.raises(AnkiConnectError, match="collection is not available"):
        client.get_deck_names()


def test_noop_fault_keeps_note_unchanged(fake: FakeServer) -> None:
    """``noop`` mimics updateNoteFields while the note is open in the browser."""
    fake.anki.faults.append(Fault(action="updateNoteFields", noop=True, times=1))
    request = {
        "action": "updateNoteFields",
        "version": 6,
        "params": {"note": {"id": 1001, "fields": {"Back": "puppy"}}},
    }
    assert fake.anki.handle(request) == {"result": None, "error": None}
    assert fake.anki.state.notes[1001].fields["Back"] == "dog"
    fake.anki.handle(request)
    assert fake.anki.state.notes[1001].fields["Back"] == "puppy"
