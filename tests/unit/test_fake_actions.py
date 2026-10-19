"""Unit tests for the fake AnkiConnect actions (no sockets)."""

import itertools
from typing import Any

import pytest

from anki_helpers.fake_anki import (
    FakeAnki,
    Fault,
    dump_state,
    load_state,
    sample_seed,
    supported_actions,
)


@pytest.fixture
def anki() -> FakeAnki:
    """Sample collection with a clock that ticks once per call."""
    ticks = itertools.count(1_000_000)
    return FakeAnki(state=load_state(sample_seed(), clock=lambda: next(ticks)))


def call(anki: FakeAnki, action: str, **params: Any) -> Any:
    """Invoke a v6 action and return its result, failing on an error."""
    reply = anki.handle({"action": action, "version": 6, "params": params})
    assert reply["error"] is None, reply["error"]
    return reply["result"]


def error(anki: FakeAnki, action: str, **params: Any) -> str:
    """Invoke a v6 action that must fail and return the error string."""
    reply = anki.handle({"action": action, "version": 6, "params": params})
    assert reply["result"] is None
    return reply["error"]


def basic(front: str, deck: str = "Spanish", **extra: Any) -> dict[str, Any]:
    """Build an addNote ``note`` param for the Basic model."""
    return {
        "deckName": deck,
        "modelName": "Basic",
        "fields": {"Front": front, "Back": "b"},
        **extra,
    }


def test_envelope_versions(anki: FakeAnki) -> None:
    """v6 wraps the result; v4 (or missing version) returns it bare."""
    assert anki.handle({"action": "version", "version": 6}) == {
        "result": 6,
        "error": None,
    }
    assert anki.handle({"action": "version"}) == 6
    assert anki.handle({"action": "nope", "version": 6}) == {
        "result": None,
        "error": "unsupported action",
    }
    assert error(anki, "deckNames", bogus=1).startswith("FakeAnki.deck_names()")


def test_supported_actions_cover_legacy_client() -> None:
    """Every action the legacy client calls is implemented."""
    needed = {"deckNames", "findNotes", "findCards", "cardsInfo", "notesInfo"}
    assert needed | {"getIntervals"} <= set(supported_actions())


def test_decks_and_models(anki: FakeAnki) -> None:
    """Deck creation adds parents; stock models are present."""
    deck_id = call(anki, "createDeck", deck="A::B::C")
    assert {"A", "A::B", "A::B::C"} <= set(call(anki, "deckNames"))
    assert call(anki, "deckNamesAndIds")["A::B::C"] == deck_id
    assert call(anki, "modelNames") == [
        "Basic",
        "Basic (and reversed card)",
        "Cloze",
    ]
    assert call(anki, "modelFieldNames", modelName="Cloze") == ["Text", "Back Extra"]
    assert error(anki, "modelFieldNames", modelName="X") == "model was not found: X"


def test_add_note_creates_cards(anki: FakeAnki) -> None:
    """Reversed model gets two cards; cloze one per cloze number."""
    nid = call(
        anki,
        "addNote",
        note={
            "deckName": "Default",
            "modelName": "Basic (and reversed card)",
            "fields": {"Front": "f", "Back": "b"},
            "tags": ["t1"],
        },
    )
    info = call(anki, "notesInfo", notes=[nid])[0]
    assert info["tags"] == ["t1"]
    assert len(info["cards"]) == 2
    cloze = {"Text": "{{c1::a}} {{c3::b}}", "Back Extra": ""}
    nid = call(
        anki,
        "addNote",
        note={"deckName": "Default", "modelName": "Cloze", "fields": cloze},
    )
    cards = call(
        anki, "cardsInfo", cards=call(anki, "notesInfo", notes=[nid])[0]["cards"]
    )
    assert [c["ord"] for c in cards] == [0, 2]
    assert '<span class="cloze">[...]</span> b' in cards[0]["question"]


def test_add_note_errors(anki: FakeAnki) -> None:
    """Duplicate, empty, unknown deck/model fail with AnkiConnect's messages."""
    dup = "cannot create note because it is a duplicate"
    assert error(anki, "addNote", note=basic("el perro")) == dup
    assert error(anki, "addNote", note=basic(" ")) == (
        "cannot create note because it is empty"
    )
    assert error(anki, "addNote", note=basic("x", deck="Nope")) == (
        "deck was not found: Nope"
    )
    assert error(anki, "addNote", note={**basic("x"), "modelName": "M"}) == (
        "model was not found: M"
    )
    # duplicateScope=deck: same front in another deck is fine
    scoped = basic("el perro", deck="Default", options={"duplicateScope": "deck"})
    assert isinstance(call(anki, "addNote", note=scoped), int)
    allowed = basic("el perro", options={"allowDuplicate": True})
    assert isinstance(call(anki, "addNote", note=allowed), int)


def test_add_notes_and_can_add(anki: FakeAnki) -> None:
    """Batch helpers report per-note results."""
    notes = [basic("uno"), basic("el perro")]
    assert call(anki, "canAddNotes", notes=notes) == [True, False]
    detail = call(anki, "canAddNotesWithErrorDetail", notes=notes)
    assert detail[0] == {"canAdd": True}
    assert detail[1]["error"] == "cannot create note because it is a duplicate"
    assert "duplicate" in error(anki, "addNotes", notes=notes)
    assert 1006 in call(anki, "findNotes", query="uno or perro")


def test_update_bumps_mod(anki: FakeAnki) -> None:
    """Field/tag updates change mod on the note and its cards."""
    before = call(anki, "notesModTime", notes=[1001])[0]["mod"]
    call(
        anki,
        "updateNote",
        note={"id": 1001, "fields": {"Back": "hound"}, "tags": ["x"]},
    )
    info = call(anki, "notesInfo", notes=[1001])[0]
    assert info["fields"]["Back"] == {"value": "hound", "order": 1}
    assert info["tags"] == ["x"]
    assert info["mod"] > before
    assert call(anki, "cardsModTime", cards=[2001])[0]["mod"] == info["mod"]
    assert error(anki, "updateNoteFields", note={"id": 9, "fields": {}}) == (
        "Note was not found: 9"
    )


def test_update_adds_cloze_cards(anki: FakeAnki) -> None:
    """A new cloze number creates a card; existing cards are kept."""
    text = "{{c1::Hola}} {{c2::x}} {{c3::y}}"
    call(anki, "updateNoteFields", note={"id": 1007, "fields": {"Text": text}})
    assert len(call(anki, "notesInfo", notes=[1007])[0]["cards"]) == 3


def test_tags(anki: FakeAnki) -> None:
    """addTags/removeTags edit tags; getTags lists all."""
    call(anki, "addTags", notes=[1001, 1002], tags="new  animals")
    assert call(anki, "getNoteTags", note=1001) == ["noun", "animals", "new"]
    call(anki, "removeTags", notes=[1001], tags="NOUN")
    assert call(anki, "getNoteTags", note=1001) == ["animals", "new"]
    assert "phrase" in call(anki, "getTags")


def test_delete_notes(anki: FakeAnki) -> None:
    """Deleting a note removes its cards; unknown ids give {} in info calls."""
    call(anki, "deleteNotes", notes=[1004])
    assert call(anki, "notesInfo", notes=[1004]) == [{}]
    assert call(anki, "cardsInfo", cards=[2004, 2005]) == [{}, {}]


def test_cards(anki: FakeAnki) -> None:
    """CardsInfo shape, intervals, suspend round trip."""
    info = call(anki, "cardsInfo", cards=[2001])[0]
    assert info["deckName"] == "German::Vocab"
    assert info["due"] == 20000 - 3
    assert info["question"] == "<b>der Hund</b>"
    assert info["answer"].endswith("dog")
    assert call(anki, "getIntervals", cards=[2001, 2006]) == [12, 0]
    assert call(anki, "cardsToNotes", cards=[2004, 2005, 2001]) == [1001, 1004]
    assert call(anki, "suspend", cards=[2001]) is True
    assert call(anki, "suspend", cards=[2001]) is False
    assert call(anki, "areSuspended", cards=[2001, 1]) == [True, None]
    assert call(anki, "findCards", query="is:suspended") == [2001, 2007]
    assert call(anki, "unsuspend", cards=[2001]) is True
    assert call(anki, "areDue", cards=[2001, 2003]) == [True, False]
    call(anki, "setSpecificValueOfCard", card=2006, keys=["flags"], newValues=[3])
    assert call(anki, "findCards", query="flag:3") == [2006]


def test_media(anki: FakeAnki) -> None:
    """Store/retrieve base64 round-trip; missing → False."""
    assert call(anki, "retrieveMediaFile", filename="hello.txt") == "aGVsbG8="
    assert call(anki, "retrieveMediaFile", filename="nope") is False
    assert call(
        anki, "storeMediaFile", filename="hello.txt", data="eA==", deleteExisting=False
    ) == ("hello-1.txt")
    assert call(anki, "getMediaFilesNames", pattern="hello*") == [
        "hello-1.txt",
        "hello.txt",
    ]
    call(anki, "deleteMediaFile", filename="hello.txt")
    assert call(anki, "getMediaFilesNames") == ["hello-1.txt"]


def test_multi(anki: FakeAnki) -> None:
    """Multi answers each action by its own version."""
    result = call(
        anki,
        "multi",
        actions=[
            {"action": "version"},
            {"action": "version", "version": 6},
            {"action": "bogus", "version": 6},
        ],
    )
    assert result == [
        6,
        {"result": 6, "error": None},
        {"result": None, "error": "unsupported action"},
    ]


def test_faults_and_log(anki: FakeAnki) -> None:
    """Faults fire the given number of times; every request is logged."""
    anki.faults.append(
        Fault(action="deckNames", error="collection is not available", times=1)
    )
    assert error(anki, "deckNames") == "collection is not available"
    assert "Default" in call(anki, "deckNames")
    assert [r["action"] for r in anki.log] == ["deckNames", "deckNames"]


def test_dump_load_round_trip(anki: FakeAnki) -> None:
    """dump_state output loads back to an identical dump."""
    call(anki, "addNote", note=basic("nuevo"))
    dumped = dump_state(anki.state)
    assert dump_state(load_state(dumped)) == dumped
