"""Fake responses have the same JSON shape as AnkiConnect's documented ones.

The reference file is hand-copied from the AnkiConnect README; S1-08 replaces
it with responses recorded from a real headless Anki.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from anki_helpers.fake_anki import FakeAnki, load_state, sample_seed

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/ankiconnect/readme_v6.json").read_text()
)

# Dicts keyed by data (names), not by schema: compare value shapes only.
MAPS = {"fields", "deckNamesAndIds", "modelNamesAndIds"}

# Keys the fake returns beyond the README example. Newer add-on versions return
# them too (⚠️ confirm with S1-08 recordings).
EXTRA_KEYS = {"cardsInfo": {"factor", "flags"}}

NEW = {"deckName": "Spanish", "modelName": "Basic", "fields": {"Front": "nuevo"}}
DUP = {"deckName": "Spanish", "modelName": "Basic", "fields": {"Front": "el perro"}}

PARAMS: dict[str, dict[str, Any]] = {
    "requestPermission": {},
    "createDeck": {"deck": "Fresh"},
    "modelFieldNames": {"modelName": "Basic"},
    "findNotes": {"query": "tag:noun"},
    "findCards": {"query": "tag:noun"},
    "notesInfo": {"notes": [1001]},
    "notesModTime": {"notes": [1001]},
    "cardsInfo": {"cards": [2001]},
    "cardsModTime": {"cards": [2001]},
    "cardsToNotes": {"cards": [2001, 2004]},
    "getIntervals": {"cards": [2001, 2002]},
    "getEaseFactors": {"cards": [2001, 2002]},
    "areSuspended": {"cards": [2001, 2007, 9]},
    "areDue": {"cards": [2001, 2003]},
    "suspend": {"cards": [2001]},
    "unsuspend": {"cards": [2007]},
    "addNote": {"note": NEW},
    "addNotes": {"notes": [{**NEW, "fields": {"Front": "a"}}]},
    "canAddNotes": {"notes": [NEW]},
    "canAddNotesWithErrorDetail": {"notes": [DUP, NEW]},
    "getNoteTags": {"note": 1001},
    "storeMediaFile": {"filename": "_hello.txt", "data": "SGVsbG8="},
    "retrieveMediaFile": {"filename": "hello.txt"},
    "getMediaFilesNames": {"pattern": "*.txt"},
    "multi": {
        "actions": [{"action": "deckNames"}, {"action": "deckNames", "version": 6}]
    },
}


def shape(value: Any, key: str = "") -> Any:
    """Reduce JSON to its type skeleton; lists keep each distinct item shape."""
    if isinstance(value, dict):
        if key in MAPS:
            return {
                "*": sorted(
                    {json.dumps(shape(v), sort_keys=True) for v in value.values()}
                )
            }
        return {k: shape(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return sorted({json.dumps(shape(v, key), sort_keys=True) for v in value})
    return type(value).__name__


def strip_extra(action: str, value: Any) -> Any:
    """Drop ``EXTRA_KEYS`` from record dicts in a result."""
    extra = EXTRA_KEYS.get(action, set())
    if isinstance(value, list):
        return [
            {k: v for k, v in item.items() if k not in extra}
            if isinstance(item, dict)
            else item
            for item in value
        ]
    return value


@pytest.fixture
def anki() -> FakeAnki:
    """Fresh sample collection."""
    return FakeAnki(state=load_state(sample_seed(), clock=lambda: 1_700_000_000))


@pytest.mark.parametrize("action", sorted(k for k in REFERENCE if k != "_source"))
def test_shape_matches_readme(anki: FakeAnki, action: str) -> None:
    """Each documented action answers with the documented JSON shape."""
    reply = anki.handle(
        {"action": action, "version": 6, "params": PARAMS.get(action, {})}
    )
    assert reply["error"] is None, reply["error"]
    fake = strip_extra(action, reply["result"])
    assert shape(fake, action) == shape(REFERENCE[action], action)


def test_extra_keys_are_present(anki: FakeAnki) -> None:
    """EXTRA_KEYS stays accurate: the fake really returns those keys."""
    info = anki.handle(
        {"action": "cardsInfo", "version": 6, "params": PARAMS["cardsInfo"]}
    )
    assert EXTRA_KEYS["cardsInfo"] <= set(info["result"][0])
