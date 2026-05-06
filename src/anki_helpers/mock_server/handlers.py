"""AnkiConnect action handlers backed by :class:`State`.

Each handler accepts the ``params`` dict the client supplied and returns a
JSON-serializable result. Failures raise ``ValueError`` whose message becomes
the ``error`` field in the AnkiConnect response envelope. The handlers
intentionally cover only what this project's CLI actually uses, plus a few
neighbouring actions (Tier-1 reads + the most common writes) so the mock
remains useful for downstream tooling.
"""

import base64
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .query import CardCtx, NoteCtx, match_card, match_note, parse_query
from .state import State

Handler = Callable[[Dict[str, Any], State], Any]
HANDLERS: Dict[str, Handler] = {}


def action(name: Optional[str] = None) -> Callable[[Handler], Handler]:
    """Register a handler under the AnkiConnect action name.

    Args:
        name: Public action name. Defaults to the function's ``__name__``.

    Returns:
        A decorator that records the handler in the global registry.
    """

    def decorator(fn: Handler) -> Handler:
        HANDLERS[name or fn.__name__] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Miscellaneous / metadata
# ---------------------------------------------------------------------------


@action()
def version(params: Dict[str, Any], state: State) -> int:
    """Return the AnkiConnect API version implemented by the mock."""
    del params, state
    return 6


@action()
def requestPermission(params: Dict[str, Any], state: State) -> Dict[str, Any]:
    """Grant permission unconditionally and mirror AnkiConnect's shape."""
    del params, state
    return {
        "permission": "granted",
        "requireApiKey": False,
        "version": 6,
    }


@action()
def sync(params: Dict[str, Any], state: State) -> None:
    """No-op stand-in for AnkiConnect's ``sync`` action."""
    del params, state
    return None


@action()
def getProfiles(params: Dict[str, Any], state: State) -> List[str]:
    """Return a single fake profile so clients that probe profiles succeed."""
    del params, state
    return ["User 1"]


@action()
def getActiveProfile(params: Dict[str, Any], state: State) -> str:
    """Return the only fake profile."""
    del params, state
    return "User 1"


@action()
def loadProfile(params: Dict[str, Any], state: State) -> bool:
    """Pretend to switch profiles."""
    del params, state
    return True


@action()
def apiReflect(params: Dict[str, Any], state: State) -> Dict[str, Any]:
    """Report the action names the mock implements."""
    del state
    requested = params.get("actions") or list(HANDLERS)
    return {
        "scopes": ["actions"],
        "actions": [name for name in requested if name in HANDLERS],
    }


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------


@action()
def deckNames(params: Dict[str, Any], state: State) -> List[str]:
    """Return all deck names ordered by id."""
    del params
    rows = state.db.execute("SELECT name FROM decks ORDER BY id")
    return [row["name"] for row in rows]


@action()
def deckNamesAndIds(params: Dict[str, Any], state: State) -> Dict[str, int]:
    """Return a mapping of deck names to ids."""
    del params
    rows = state.db.execute("SELECT id, name FROM decks ORDER BY id")
    return {row["name"]: row["id"] for row in rows}


@action()
def createDeck(params: Dict[str, Any], state: State) -> int:
    """Create a deck (idempotent) and return its id."""
    name = params["deck"]
    return state.get_or_create_deck(name)


@action()
def changeDeck(params: Dict[str, Any], state: State) -> None:
    """Move the listed cards into ``deck`` (creating it if needed)."""
    state.change_card_deck(params.get("cards", []), params["deck"])
    return None


@action()
def deleteDecks(params: Dict[str, Any], state: State) -> None:
    """Delete decks; ``cardsToo`` must be true (mirroring real AnkiConnect)."""
    if not params.get("cardsToo"):
        raise ValueError("cardsToo must be set to true")
    deck_names = params.get("decks") or []
    for name in deck_names:
        deck_id = state.get_deck_id(name)
        if deck_id is None:
            continue
        note_ids = [
            row["id"]
            for row in state.db.execute(
                "SELECT id FROM notes WHERE deck_id = ?", (deck_id,)
            )
        ]
        state.delete_notes(note_ids)
        state.db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@action()
def modelNames(params: Dict[str, Any], state: State) -> List[str]:
    """Return all known note-type names."""
    del params
    rows = state.db.execute("SELECT name FROM models ORDER BY id")
    return [row["name"] for row in rows]


@action()
def modelNamesAndIds(params: Dict[str, Any], state: State) -> Dict[str, int]:
    """Return a mapping of model names to ids."""
    del params
    rows = state.db.execute("SELECT id, name FROM models ORDER BY id")
    return {row["name"]: row["id"] for row in rows}


@action()
def modelFieldNames(params: Dict[str, Any], state: State) -> List[str]:
    """Return the ordered field names for a model."""
    model = state.get_model(params["modelName"])
    if model is None:
        raise ValueError(f"model was not found: {params['modelName']}")
    return list(json.loads(model["fields_json"]))


# ---------------------------------------------------------------------------
# Notes (read)
# ---------------------------------------------------------------------------


@action()
def findNotes(params: Dict[str, Any], state: State) -> List[int]:
    """Return note ids matching ``query`` using the supported DSL subset."""
    tokens = parse_query(params.get("query", ""))
    note_rows = state.all_note_rows()
    cards_by_note = _group_cards_by_note(state)
    out: List[int] = []
    for note in note_rows:
        ctx = NoteCtx(note=dict(note), cards=cards_by_note.get(note["id"], []))
        if match_note(tokens, ctx):
            out.append(note["id"])
    return out


@action()
def notesInfo(params: Dict[str, Any], state: State) -> List[Dict[str, Any]]:
    """Return enriched note objects for the supplied ids or query."""
    note_ids = list(params.get("notes") or [])
    if not note_ids and params.get("query"):
        note_ids = findNotes({"query": params["query"]}, state)
    note_ids_set = set(note_ids)
    out: List[Dict[str, Any]] = []
    cards_by_note = _group_cards_by_note(state)
    for note in state.all_note_rows():
        if note["id"] not in note_ids_set:
            continue
        order = {
            field_name: index
            for index, field_name in enumerate(json.loads(note["model_fields"]))
        }
        fields = {
            name: {"value": value, "order": order.get(name, 0)}
            for name, value in json.loads(note["fields_json"]).items()
        }
        out.append(
            {
                "noteId": note["id"],
                "profile": "User 1",
                "modelName": note["model_name"],
                "tags": json.loads(note["tags_json"]),
                "fields": fields,
                "mod": note["mod"],
                "cards": [card["id"] for card in cards_by_note.get(note["id"], [])],
            }
        )
    by_id = {item["noteId"]: item for item in out}
    return [by_id[nid] for nid in note_ids if nid in by_id]


@action()
def canAddNotes(params: Dict[str, Any], state: State) -> List[bool]:
    """Return per-note booleans indicating whether ``addNote`` would succeed."""
    out: List[bool] = []
    for spec in params.get("notes", []):
        try:
            deck_id = state.get_deck_id(spec["deckName"])
            model = state.get_model(spec["modelName"])
            if deck_id is None or model is None:
                out.append(False)
                continue
            field_order = json.loads(model["fields_json"])
            first = (spec["fields"].get(field_order[0]) or "").strip()
            if not first:
                out.append(False)
                continue
            if state._has_duplicate_first_field(  # noqa: SLF001
                deck_id, model["id"], field_order[0], first
            ):
                out.append(False)
                continue
            out.append(True)
        except Exception:
            out.append(False)
    return out


@action()
def getTags(params: Dict[str, Any], state: State) -> List[str]:
    """Return a sorted list of every tag in use."""
    del params
    return state.get_all_tags()


# ---------------------------------------------------------------------------
# Notes (write)
# ---------------------------------------------------------------------------


@action()
def addNote(params: Dict[str, Any], state: State) -> int:
    """Insert a single note and return its new id."""
    note = params["note"]
    options = note.get("options") or {}
    return state.add_note(
        deck_name=note["deckName"],
        model_name=note["modelName"],
        fields=note["fields"],
        tags=note.get("tags"),
        allow_duplicate=bool(options.get("allowDuplicate", False)),
    )


@action()
def addNotes(params: Dict[str, Any], state: State) -> List[Optional[int]]:
    """Bulk insert; returns one id per input, ``None`` for failures."""
    out: List[Optional[int]] = []
    for spec in params.get("notes", []):
        try:
            out.append(addNote({"note": spec}, state))
        except ValueError:
            out.append(None)
    return out


@action()
def updateNoteFields(params: Dict[str, Any], state: State) -> None:
    """Patch the fields on an existing note."""
    note = params["note"]
    state.update_note_fields(note["id"], note["fields"])
    return None


@action()
def updateNoteTags(params: Dict[str, Any], state: State) -> None:
    """Replace the tag list on an existing note."""
    state.update_note_tags(params["note"], list(params.get("tags") or []))
    return None


@action()
def updateNote(params: Dict[str, Any], state: State) -> None:
    """Update fields and/or tags on a note (whichever are provided)."""
    note = params["note"]
    if "fields" in note:
        state.update_note_fields(note["id"], note["fields"])
    if "tags" in note:
        state.update_note_tags(note["id"], list(note.get("tags") or []))
    return None


@action()
def deleteNotes(params: Dict[str, Any], state: State) -> None:
    """Delete the listed notes (cards cascade)."""
    state.delete_notes(params.get("notes", []))
    return None


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@action()
def findCards(params: Dict[str, Any], state: State) -> List[int]:
    """Return card ids matching ``query``."""
    tokens = parse_query(params.get("query", ""))
    notes_by_id = {row["id"]: dict(row) for row in state.all_note_rows()}
    out: List[int] = []
    for card in state.all_card_rows():
        note = notes_by_id.get(card["note_id"])
        if note is None:
            continue
        ctx = CardCtx(card=dict(card), note=note)
        if match_card(tokens, ctx):
            out.append(card["id"])
    return out


@action()
def cardsInfo(params: Dict[str, Any], state: State) -> List[Dict[str, Any]]:
    """Return enriched card objects for the supplied card ids."""
    requested = list(params.get("cards") or [])
    if not requested:
        return []
    requested_set = set(requested)
    notes_by_id = {row["id"]: dict(row) for row in state.all_note_rows()}
    out_by_id: Dict[int, Dict[str, Any]] = {}
    for card in state.all_card_rows():
        if card["id"] not in requested_set:
            continue
        note = notes_by_id.get(card["note_id"])
        if note is None:
            continue
        order = {
            field_name: index
            for index, field_name in enumerate(json.loads(note["model_fields"]))
        }
        fields = {
            name: {"value": value, "order": order.get(name, 0)}
            for name, value in json.loads(note["fields_json"]).items()
        }
        out_by_id[card["id"]] = {
            "cardId": card["id"],
            "note": card["note_id"],
            "deckName": card["deck_name"],
            "modelName": note["model_name"],
            "fieldOrder": 0,
            "fields": fields,
            "question": _render_question(fields),
            "answer": _render_answer(fields),
            "ord": card["ord"],
            "type": int(card["queue"]),
            "queue": int(card["queue"]),
            "due": int(card["due"]),
            "interval": int(card["ivl"]),
            "factor": int(card["factor"]),
            "reps": int(card["reps"]),
            "lapses": int(card["lapses"]),
            "flags": int(card["flags"]),
            "suspended": bool(card["suspended"]),
            "mod": int(note["mod"]),
        }
    return [out_by_id[cid] for cid in requested if cid in out_by_id]


@action()
def getIntervals(params: Dict[str, Any], state: State) -> List[int]:
    """Return the ``ivl`` value for each requested card id (in order)."""
    card_ids = list(params.get("cards") or [])
    if not card_ids:
        return []
    placeholders = ",".join("?" for _ in card_ids)
    rows = state.db.execute(
        f"SELECT id, ivl FROM cards WHERE id IN ({placeholders})", card_ids
    ).fetchall()
    by_id = {row["id"]: int(row["ivl"]) for row in rows}
    return [by_id.get(cid, 0) for cid in card_ids]


@action()
def areSuspended(params: Dict[str, Any], state: State) -> List[Optional[bool]]:
    """Return suspension status per card id (``None`` for unknown ids)."""
    card_ids = list(params.get("cards") or [])
    if not card_ids:
        return []
    placeholders = ",".join("?" for _ in card_ids)
    rows = state.db.execute(
        f"SELECT id, suspended FROM cards WHERE id IN ({placeholders})",
        card_ids,
    ).fetchall()
    by_id = {row["id"]: bool(row["suspended"]) for row in rows}
    out: List[Optional[bool]] = []
    for cid in card_ids:
        out.append(by_id.get(cid))
    return out


@action()
def suspend(params: Dict[str, Any], state: State) -> bool:
    """Suspend the listed cards."""
    return _set_suspended(params.get("cards", []), True, state)


@action()
def unsuspend(params: Dict[str, Any], state: State) -> bool:
    """Unsuspend the listed cards."""
    return _set_suspended(params.get("cards", []), False, state)


# ---------------------------------------------------------------------------
# Media (lightweight)
# ---------------------------------------------------------------------------


@action()
def storeMediaFile(params: Dict[str, Any], state: State) -> str:
    """Store a media file (only ``data`` base64 is supported)."""
    filename = params["filename"]
    if "data" in params and params["data"]:
        blob = base64.b64decode(params["data"])
    elif "path" in params and params["path"]:
        blob = Path(params["path"]).read_bytes()
    else:
        raise ValueError("storeMediaFile requires either 'data' or 'path'")
    state.db.execute(
        "INSERT OR REPLACE INTO media(filename, data) VALUES (?, ?)",
        (filename, blob),
    )
    return filename


@action()
def retrieveMediaFile(params: Dict[str, Any], state: State) -> Optional[str]:
    """Return base64-encoded contents for the named media file (or false)."""
    row = state.db.execute(
        "SELECT data FROM media WHERE filename = ?", (params["filename"],)
    ).fetchone()
    if row is None:
        return None
    return base64.b64encode(row["data"]).decode("ascii")


@action()
def deleteMediaFile(params: Dict[str, Any], state: State) -> None:
    """Remove a media file from the mock store."""
    state.db.execute("DELETE FROM media WHERE filename = ?", (params["filename"],))
    return None


@action()
def getMediaFilesNames(params: Dict[str, Any], state: State) -> List[str]:
    """Return matching media filenames; supports a ``pattern`` glob."""
    pattern = params.get("pattern") or "*"
    sql_pattern = pattern.replace("*", "%")
    rows = state.db.execute(
        "SELECT filename FROM media WHERE filename LIKE ? ORDER BY filename",
        (sql_pattern,),
    )
    return [row["filename"] for row in rows]


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


@action()
def multi(params: Dict[str, Any], state: State) -> List[Dict[str, Any]]:
    """Run a list of sub-actions, returning one envelope each."""
    out: List[Dict[str, Any]] = []
    for sub in params.get("actions", []):
        sub_action = sub.get("action", "")
        handler = HANDLERS.get(sub_action)
        if handler is None:
            out.append({"result": None, "error": "unsupported action"})
            continue
        try:
            out.append({"result": handler(sub.get("params", {}), state), "error": None})
        except Exception as exc:  # noqa: BLE001
            out.append({"result": None, "error": str(exc)})
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _group_cards_by_note(state: State) -> Dict[int, List[Dict[str, Any]]]:
    """Build a ``{note_id: [card_dict, ...]}`` map for query evaluation."""
    out: Dict[int, List[Dict[str, Any]]] = {}
    for card in state.all_card_rows():
        out.setdefault(card["note_id"], []).append(dict(card))
    return out


def _render_question(fields: Dict[str, Dict[str, Any]]) -> str:
    """Cheap stand-in for the rendered card front."""
    first = next(iter(fields.values()), None)
    return first["value"] if first else ""


def _render_answer(fields: Dict[str, Dict[str, Any]]) -> str:
    """Cheap stand-in for the rendered card back."""
    values = [item["value"] for item in fields.values()]
    return "<hr>".join(values)


def _set_suspended(card_ids: List[int], suspended: bool, state: State) -> bool:
    """Toggle the ``suspended`` flag on the given cards."""
    if not card_ids:
        return True
    placeholders = ",".join("?" for _ in card_ids)
    state.db.execute(
        f"UPDATE cards SET suspended = ? WHERE id IN ({placeholders})",
        [1 if suspended else 0, *card_ids],
    )
    return True
