"""Record read-only AnkiConnect v6 responses from a running Anki (S1-08).

Usage: uv run python tests/fixtures/ankiconnect/record.py [URL]

Writes ``recorded_v6.json`` next to this file. Only read-only actions are
called, so the collection is not modified. Values are raw except: id and file
lists are cut to ``KEEP`` items and media base64 to 64 chars (shapes unchanged).
"""

import json
import sys
from pathlib import Path
from typing import Any

import requests

OUT = Path(__file__).with_name("recorded_v6.json")
KEEP = 5
MISSING_CARD = 9


def invoke(url: str, action: str, **params: Any) -> Any:
    """Call one action and return its result, raising on an AnkiConnect error."""
    reply = requests.post(
        url, json={"action": action, "version": 6, "params": params}, timeout=30
    ).json()
    if reply["error"] is not None:
        raise RuntimeError(f"{action}: {reply['error']}")
    return reply["result"]


def record(url: str) -> dict[str, Any]:
    """Pick real ids from the collection and record each read-only action."""
    # Tagged cards, so tag lists record their item shape instead of [].
    cards: list[int] = invoke(url, "findCards", query="flag:1 -tag:none")[:2]
    if len(cards) < 2:
        cards = invoke(url, "findCards", query="-tag:none")[:2]
    suspended: list[int] = invoke(url, "findCards", query="is:suspended")[:1]
    note: dict[str, Any] = invoke(
        url, "notesInfo", notes=[invoke(url, "cardsToNotes", cards=cards[:1])[0]]
    )[0]
    deck: str = invoke(url, "cardsInfo", cards=cards[:1])[0]["deckName"]
    first = min(note["fields"], key=lambda f: note["fields"][f]["order"])
    dup = {
        "deckName": deck,
        "modelName": note["modelName"],
        "fields": {first: note["fields"][first]["value"]},
    }
    new = {**dup, "fields": {first: "anki-helpers S1-08 probe, never added"}}
    media: list[str] = invoke(url, "getMediaFilesNames", pattern="*")[:KEEP]

    params: dict[str, dict[str, Any]] = {
        "version": {},
        "requestPermission": {},
        "deckNames": {},
        "deckNamesAndIds": {},
        "modelNames": {},
        "modelNamesAndIds": {},
        "modelFieldNames": {"modelName": note["modelName"]},
        "getTags": {},
        "findCards": {"query": "flag:1"},
        "findNotes": {"query": "flag:1"},
        "cardsInfo": {"cards": cards},
        "cardsModTime": {"cards": cards},
        "cardsToNotes": {"cards": cards},
        "notesInfo": {"notes": [note["noteId"]]},
        "notesModTime": {"notes": [note["noteId"]]},
        "getNoteTags": {"note": note["noteId"]},
        "getIntervals": {"cards": cards},
        "getEaseFactors": {"cards": cards},
        "areSuspended": {"cards": [*cards[:1], *suspended, MISSING_CARD]},
        "areDue": {"cards": cards},
        "canAddNotes": {"notes": [new]},
        "canAddNotesWithErrorDetail": {"notes": [dup, new]},
        "getMediaFilesNames": {"pattern": "*"},
        "retrieveMediaFile": {"filename": media[0]}
        if media
        else {"filename": "_missing"},
        "multi": {
            "actions": [{"action": "deckNames"}, {"action": "deckNames", "version": 6}]
        },
    }
    out: dict[str, Any] = {}
    for action, p in params.items():
        result = invoke(url, action, **p)
        if action in {"findCards", "findNotes", "getMediaFilesNames"}:
            result = result[:KEEP]
        if action == "retrieveMediaFile" and isinstance(result, str):
            result = result[:64]
        out[action] = result
    return out


def main() -> None:
    """Record from the URL in argv (default localhost) and write ``OUT``."""
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
    doc = {
        "_source": (
            "Responses recorded from a real Anki + AnkiConnect (API v6) by record.py. "
            f"Read-only actions only; id/file lists cut to {KEEP}, media base64 to 64 chars."
        ),
        **record(url),
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"Recorded {len(doc) - 1} actions to {OUT}")


if __name__ == "__main__":
    main()
