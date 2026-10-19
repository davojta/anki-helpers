"""Unit tests for the fake AnkiConnect search engine."""

import pytest

from anki_helpers.fake_anki import SearchError, load_state, sample_seed
from anki_helpers.fake_anki.search import find_cards, find_notes, tokenize
from anki_helpers.fake_anki.state import State


@pytest.fixture
def state() -> State:
    """The bundled sample collection with a fixed clock."""
    return load_state(sample_seed(), clock=lambda: 1_000_000)


def test_tokenize_quotes_and_parens() -> None:
    """Quotes group words and disappear; parens are separate tokens."""
    assert tokenize('"deck:My Deck" -(tag:a or b)') == [
        "deck:My Deck",
        "-",
        "(",
        "tag:a",
        "or",
        "b",
        ")",
    ]
    assert tokenize('deck:"A B"') == ["deck:A B"]


@pytest.mark.parametrize(
    ("query", "notes"),
    [
        ("", [1001, 1002, 1003, 1004, 1005, 1006, 1007]),
        ("flag:1", [1001, 1002, 1003, 1004, 1007]),
        ("flag:2", [1004]),
        ("flag:0", [1005, 1006, 1007]),
        ("deck:German", [1001, 1002, 1003, 1004, 1005]),
        ("deck:german::vocab", [1001, 1002, 1003, 1004, 1005]),
        ("deck:Germ*", [1001, 1002, 1003, 1004, 1005]),
        ("deck:Vocab", []),
        ("tag:animals", [1001, 1002, 1006]),
        ("tag:none", []),
        ("-tag:noun", [1003, 1004, 1007]),
        ("tag:noun -deck:Spanish", [1001, 1002, 1005]),
        ("tag:verb or tag:adjective", [1003, 1004]),
        ("deck:Spanish (tag:phrase or is:suspended)", [1006, 1007]),
        ("-(deck:German or deck:Spanish)", []),
        ("dog", [1001, 1006]),
        ("hund", [1001]),
        ("d_g", [1001, 1006]),
        ("front:dog", []),
        ("back:dog", [1001, 1006]),
        ("Front:die*", [1002]),
        ("note:Cloze", [1007]),
        ("note:basic*", [1001, 1002, 1003, 1004, 1005, 1006]),
        ("card:2", [1004, 1007]),
        ("nid:1001,1003", [1001, 1003]),
        ("cid:2005", [1004]),
        ("is:new", [1005, 1007]),
        ("is:suspended", [1006]),
        ("is:review", [1001, 1002, 1003, 1004, 1006, 1007]),
        ("is:due", [1001, 1002, 1004]),
        ("flag:1 prop:due<0 prop:due>-7", [1001]),
        ("flag:1 prop:due<-6", []),
        ("prop:due<-6", [1004]),
        ("flag:1 prop:due=0", [1002]),
        ("prop:due=2", []),  # suspended card has no due day
        ("prop:ivl>=20", [1003, 1004]),
        ("prop:lapses>0", [1002, 1004]),
        ("prop:ease<2", [1004]),
        ("prop:reps!=0", [1001, 1002, 1003, 1004, 1006, 1007]),
    ],
)
def test_find_notes(state: State, query: str, notes: list[int]) -> None:
    """Each query matches the expected notes of the sample collection."""
    assert find_notes(state, query) == notes


def test_find_cards_is_card_level(state: State) -> None:
    """Card-level terms select single cards of multi-card notes."""
    assert find_cards(state, "nid:1004") == [2004, 2005]
    assert find_cards(state, "nid:1004 flag:2") == [2005]
    assert find_cards(state, "note:Cloze is:new") == [2009]


def test_edited_uses_clock(state: State) -> None:
    """edited:N compares note mod to the injected clock."""
    state.notes[1001].mod = 1_000_000 - 3600
    state.notes[1002].mod = 1_000_000 - 3 * 86_400
    assert 1001 in find_notes(state, "edited:1")
    assert 1002 not in find_notes(state, "edited:1")


@pytest.mark.parametrize(
    "query",
    ["added:1", "is:bogus", "prop:foo>1", "prop:due", "(tag:a", "tag:a)", "or", 'x"y'],
)
def test_unsupported_or_invalid(state: State, query: str) -> None:
    """Unknown syntax fails loudly instead of matching silently."""
    with pytest.raises(SearchError):
        find_notes(state, query)
