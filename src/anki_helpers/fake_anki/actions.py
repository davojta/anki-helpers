"""AnkiConnect v6 actions served from the in-memory ``State``.

Error strings copy the real add-on where known, so client code sees the same
failures it would against Anki.
"""

import base64
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from . import search
from .state import Card, Model, Note, State

API_VERSION = 6

Handler = Callable[..., Any]
_ACTIONS: dict[str, Handler] = {}


def action(name: str) -> Callable[[Handler], Handler]:
    """Register a ``FakeAnki`` method as the handler of an AnkiConnect action."""

    def register(fn: Handler) -> Handler:
        _ACTIONS[name] = fn
        return fn

    return register


def supported_actions() -> list[str]:
    """Return the names of all actions the fake implements."""
    return sorted(_ACTIONS)


@dataclass
class Fault:
    """An injected failure for one action (``*`` = any action)."""

    action: str
    error: str | None = None
    latency_ms: int = 0
    times: int | None = None  # None = forever
    # Answer success without running the action, like updateNoteFields while
    # the note is open in Anki's browser.
    noop: bool = False


@dataclass
class FakeAnki:
    """Dispatches AnkiConnect requests against a ``State``. Thread-safe."""

    state: State = field(default_factory=State)
    log: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    faults: list[Fault] = field(default_factory=list[Fault])
    lock: threading.RLock = field(default_factory=threading.RLock)

    # --- envelope -------------------------------------------------------------

    def handle(self, request: dict[str, Any]) -> Any:
        """Answer one request body like AnkiConnect's ``handler``.

        Version ≥ 5 → ``{"result", "error"}``; version ≤ 4 (or missing) → the
        bare result, or ``{"result": None, "error"}`` on failure.
        """
        with self.lock:
            self.log.append(request)
        name = str(request.get("action", ""))
        version = 4
        try:
            version = int(request.get("version", 4))
            params = cast("dict[str, Any]", request.get("params") or {})
            noop = self._apply_faults(name)
            fn = _ACTIONS.get(name)
            if fn is None:
                raise Exception("unsupported action")
            with self.lock:
                result = None if noop else fn(self, **params)
        except Exception as e:
            return {"result": None, "error": str(e)}
        if version <= 4:
            return result
        return {"result": result, "error": None}

    def _apply_faults(self, name: str) -> bool:
        """Sleep/raise per the first matching fault; return its ``noop``."""
        with self.lock:
            self.faults[:] = [f for f in self.faults if f.times is None or f.times > 0]
            fault = next((f for f in self.faults if f.action in (name, "*")), None)
            if fault is None:
                return False
            if fault.times is not None:
                fault.times -= 1
                if fault.times <= 0:
                    self.faults.remove(fault)
        if fault.latency_ms:
            time.sleep(fault.latency_ms / 1000)
        if fault.error:
            raise Exception(fault.error)
        return fault.noop

    # --- helpers --------------------------------------------------------------

    def _note(self, note_id: int) -> Note:
        note = self.state.notes.get(int(note_id))
        if note is None:
            raise Exception(f"Note was not found: {note_id}")
        return note

    def _model(self, name: str) -> Model:
        model = self.state.models.get(name)
        if model is None:
            raise Exception(f"model was not found: {name}")
        return model

    def _touch(self, note: Note) -> None:
        note.mod = self.state.clock()
        for card in self.state.cards_of(note.id):
            card.mod = note.mod

    def _sync_cards(self, note: Note, deck: str) -> None:
        """Create cards for template ords the note gained (never deletes)."""
        have = {c.ord for c in self.state.cards_of(note.id)}
        for ord_ in self.state.card_ords(note):
            if ord_ not in have:
                card = Card(
                    id=self.state.new_id(), note_id=note.id, deck=deck, ord=ord_,
                    mod=note.mod, due=len(self.state.cards),
                )  # fmt: skip
                self.state.cards[card.id] = card

    def _duplicate_or_error(self, note: dict[str, Any]) -> str | None:
        """Return the error ``addNote`` would raise for ``note``, or None."""
        model = self._model(str(note.get("modelName")))
        deck = str(note.get("deckName"))
        if deck not in self.state.decks:
            return f"deck was not found: {deck}"
        fields = cast("dict[str, str]", note.get("fields", {}))
        unknown = [f for f in fields if f not in model.fields]
        if unknown:
            return f"field was not found in model: {unknown[0]}"  # ⚠️ wording
        first = fields.get(model.fields[0], "")
        probe = Note(0, model.name, {f: fields.get(f, "") for f in model.fields}, [], 0)
        if not first.strip() or not self.state.card_ords(probe):
            return "cannot create note because it is empty"
        options = cast("dict[str, Any]", note.get("options") or {})
        if options.get("allowDuplicate"):
            return None
        in_deck = options.get("duplicateScope") == "deck"
        for other in self.state.notes.values():
            if other.model != model.name:
                continue
            if next(iter(other.fields.values())).strip() != first.strip():
                continue
            if in_deck and all(c.deck != deck for c in self.state.cards_of(other.id)):
                continue
            return "cannot create note because it is a duplicate"
        return None

    def _render(self, model: Model, note: Note, ord_: int) -> tuple[str, str]:
        tmpl = model.templates[0 if model.is_cloze else ord_]

        def fill(fmt: str, front: str = "") -> str:
            def sub(m: re.Match[str]) -> str:
                name = m.group(1)
                if name == "FrontSide":
                    return front
                if name.startswith("cloze:"):
                    return _cloze(note.fields.get(name[6:], ""), ord_ + 1, front != "")
                return note.fields.get(name.split(":")[-1], "")

            return re.sub(r"\{\{([^}#/^]+)\}\}", sub, fmt)

        question = fill(tmpl.front)
        return question, fill(tmpl.back, question or " ")

    def _note_info(self, note: Note) -> dict[str, Any]:
        return {
            "noteId": note.id,
            "profile": "User 1",
            "modelName": note.model,
            "tags": list(note.tags),
            "fields": {
                k: {"value": v, "order": i}
                for i, (k, v) in enumerate(note.fields.items())
            },
            "mod": note.mod,
            "cards": [c.id for c in self.state.cards_of(note.id)],
        }

    def _card_info(self, card: Card) -> dict[str, Any]:
        note = self.state.notes[card.note_id]
        model = self.state.models[note.model]
        question, answer = self._render(model, note, card.ord)
        reviewing = card.queue in (2, 3)
        return {
            "cardId": card.id,
            "note": note.id,
            "deckName": card.deck,
            "modelName": model.name,
            "fieldOrder": card.ord,
            "ord": card.ord,
            "fields": {
                k: {"value": v, "order": i}
                for i, (k, v) in enumerate(note.fields.items())
            },
            "question": question,
            "answer": answer,
            "css": model.css,
            "interval": card.interval,
            "factor": card.factor,
            "type": card.type,
            "queue": card.queue,
            "due": self.state.today + card.due if reviewing else card.due,
            "reps": card.reps,
            "lapses": card.lapses,
            "left": 0,
            "mod": card.mod,
            "flags": card.flags,
        }

    # --- misc -----------------------------------------------------------------

    @action("version")
    def version(self) -> int:
        """Return the AnkiConnect API version."""
        return API_VERSION

    @action("requestPermission")
    def request_permission(self, **_: Any) -> dict[str, Any]:
        """Always grant permission."""
        return {"permission": "granted", "requireApikey": False, "version": API_VERSION}

    @action("sync")
    def sync(self) -> None:
        """No-op: there is no AnkiWeb."""

    @action("multi")
    def multi(self, actions: list[dict[str, Any]]) -> list[Any]:
        """Run several actions; each item follows its own ``version``."""
        return [self.handle(a) for a in actions]

    # --- decks ----------------------------------------------------------------

    @action("deckNames")
    def deck_names(self) -> list[str]:
        """Return all deck names."""
        return sorted(self.state.decks)

    @action("deckNamesAndIds")
    def deck_names_and_ids(self) -> dict[str, int]:
        """Return deck name → id."""
        return dict(sorted(self.state.decks.items()))

    @action("createDeck")
    def create_deck(self, deck: str) -> int:
        """Create a deck (and its parents); return its id."""
        return self.state.ensure_deck(deck)

    @action("deleteDecks")
    def delete_decks(self, decks: list[str], cardsToo: bool = False) -> None:
        """Delete decks, their subdecks and their cards; drop notes left cardless."""
        if not cardsToo:
            raise Exception(
                "Since Anki 2.1.28 it's not possible to delete decks without deleting cards as well"
            )
        doomed = {
            d for d in self.state.decks
            if any(d == x or d.startswith(x + "::") for x in decks)
        }  # fmt: skip
        cards = [c for c in self.state.cards.values() if c.deck in doomed]
        for card in cards:
            del self.state.cards[card.id]
        left = {c.note_id for c in self.state.cards.values()}
        self.delete_notes(sorted({c.note_id for c in cards} - left))
        for d in doomed:
            del self.state.decks[d]

    @action("changeDeck")
    def change_deck(self, cards: list[int], deck: str) -> None:
        """Move cards to a deck, creating it if needed."""
        self.state.ensure_deck(deck)
        for cid in cards:
            if cid in self.state.cards:
                self.state.cards[cid].deck = deck

    # --- models ---------------------------------------------------------------

    @action("modelNames")
    def model_names(self) -> list[str]:
        """Return all note type names."""
        return sorted(self.state.models)

    @action("modelNamesAndIds")
    def model_names_and_ids(self) -> dict[str, int]:
        """Return note type name → id."""
        return {
            m.name: m.id
            for m in sorted(self.state.models.values(), key=lambda m: m.name)
        }

    @action("modelFieldNames")
    def model_field_names(self, modelName: str) -> list[str]:
        """Return the field names of a note type."""
        return list(self._model(modelName).fields)

    # --- search ---------------------------------------------------------------

    @action("findNotes")
    def find_notes(self, query: str) -> list[int]:
        """Return note ids matching an Anki search query."""
        return search.find_notes(self.state, query)

    @action("findCards")
    def find_cards(self, query: str) -> list[int]:
        """Return card ids matching an Anki search query."""
        return search.find_cards(self.state, query)

    # --- notes ----------------------------------------------------------------

    @action("notesInfo")
    def notes_info(
        self, notes: list[int] | None = None, query: str | None = None
    ) -> list[dict[str, Any]]:
        """Return note details; unknown ids yield ``{}``."""
        ids = notes if notes is not None else self.find_notes(query or "")
        return [
            self._note_info(self.state.notes[n]) if n in self.state.notes else {}
            for n in ids
        ]

    @action("notesModTime")
    def notes_mod_time(self, notes: list[int]) -> list[dict[str, int]]:
        """Return ``{"noteId", "mod"}`` per known note."""
        return [
            {"noteId": n, "mod": self.state.notes[n].mod}
            for n in notes
            if n in self.state.notes
        ]

    @action("addNote")
    def add_note(self, note: dict[str, Any]) -> int:
        """Add one note; return its id."""
        error = self._duplicate_or_error(note)
        if error:
            raise Exception(error)
        model = self._model(str(note["modelName"]))
        fields = cast("dict[str, str]", note.get("fields", {}))
        new = Note(
            id=self.state.new_id(),
            model=model.name,
            fields={f: fields.get(f, "") for f in model.fields},
            tags=[str(t) for t in cast("list[Any]", note.get("tags") or [])],
            mod=self.state.clock(),
        )
        self.state.notes[new.id] = new
        self._sync_cards(new, str(note["deckName"]))
        return new.id

    @action("addNotes")
    def add_notes(self, notes: list[dict[str, Any]]) -> list[int | None]:
        """Add notes; if any fail, raise the list of errors.

        Like AnkiConnect, notes that succeeded stay added.
        """
        ids: list[int | None] = []
        errors: list[str] = []
        for n in notes:
            try:
                ids.append(self.add_note(n))
            except Exception as e:
                ids.append(None)
                errors.append(str(e))
        if errors:
            raise Exception(str(errors))
        return ids

    @action("canAddNotes")
    def can_add_notes(self, notes: list[dict[str, Any]]) -> list[bool]:
        """Return whether each note could be added."""
        return [not self._safe_error(n) for n in notes]

    @action("canAddNotesWithErrorDetail")
    def can_add_notes_with_error_detail(
        self, notes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return ``{"canAdd", "error"?}`` per note."""
        out: list[dict[str, Any]] = []
        for n in notes:
            error = self._safe_error(n)
            out.append({"canAdd": False, "error": error} if error else {"canAdd": True})
        return out

    def _safe_error(self, note: dict[str, Any]) -> str | None:
        try:
            return self._duplicate_or_error(note)
        except Exception as e:
            return str(e)

    @action("updateNoteFields")
    def update_note_fields(self, note: dict[str, Any]) -> None:
        """Update fields of an existing note."""
        target = self._note(int(note["id"]))
        fields = cast("dict[str, str]", note.get("fields", {}))
        for k, v in fields.items():
            if k in target.fields:
                target.fields[k] = v
        decks = [c.deck for c in self.state.cards_of(target.id)] or ["Default"]
        self._touch(target)
        self._sync_cards(target, decks[0])

    @action("updateNoteTags")
    def update_note_tags(self, note: int, tags: list[str]) -> None:
        """Replace all tags of a note."""
        target = self._note(note)
        target.tags = list(dict.fromkeys(tags))
        self._touch(target)

    @action("updateNote")
    def update_note(self, note: dict[str, Any]) -> None:
        """Update fields, then tags (fields are not rolled back on tag errors)."""
        if "fields" not in note and "tags" not in note:
            raise Exception('Must provide a "fields" or "tags" property.')
        if "fields" in note:
            self.update_note_fields(note)
        if "tags" in note:
            self.update_note_tags(int(note["id"]), list(note["tags"]))

    @action("getNoteTags")
    def get_note_tags(self, note: int) -> list[str]:
        """Return the tags of a note."""
        return list(self._note(note).tags)

    @action("addTags")
    def add_tags(self, notes: list[int], tags: str) -> None:
        """Add space-separated tags to notes."""
        for n in notes:
            if n in self.state.notes:
                target = self.state.notes[n]
                target.tags = list(dict.fromkeys([*target.tags, *tags.split()]))
                self._touch(target)

    @action("removeTags")
    def remove_tags(self, notes: list[int], tags: str) -> None:
        """Remove space-separated tags from notes (case-insensitive)."""
        drop = {t.lower() for t in tags.split()}
        for n in notes:
            if n in self.state.notes:
                target = self.state.notes[n]
                target.tags = [t for t in target.tags if t.lower() not in drop]
                self._touch(target)

    @action("getTags")
    def get_tags(self) -> list[str]:
        """Return all tags in use."""
        return sorted({t for n in self.state.notes.values() for t in n.tags})

    @action("deleteNotes")
    def delete_notes(self, notes: list[int]) -> None:
        """Delete notes and their cards."""
        for n in notes:
            self.state.notes.pop(n, None)
        for cid in [c.id for c in self.state.cards.values() if c.note_id in notes]:
            del self.state.cards[cid]

    # --- cards ----------------------------------------------------------------

    @action("cardsInfo")
    def cards_info(self, cards: list[int]) -> list[dict[str, Any]]:
        """Return card details; unknown ids yield ``{}``."""
        return [
            self._card_info(self.state.cards[c]) if c in self.state.cards else {}
            for c in cards
        ]

    @action("cardsToNotes")
    def cards_to_notes(self, cards: list[int]) -> list[int]:
        """Return the distinct note ids of cards."""
        return sorted(
            {self.state.cards[c].note_id for c in cards if c in self.state.cards}
        )

    @action("cardsModTime")
    def cards_mod_time(self, cards: list[int]) -> list[dict[str, int]]:
        """Return ``{"cardId", "mod"}`` per known card."""
        return [
            {"cardId": c, "mod": self.state.cards[c].mod}
            for c in cards
            if c in self.state.cards
        ]

    @action("getIntervals")
    def get_intervals(self, cards: list[int], complete: bool = False) -> list[Any]:
        """Return the current interval (days) of each card."""
        if complete:
            return [[self.state.cards[c].interval] for c in cards]
        return [self.state.cards[c].interval for c in cards]

    @action("getEaseFactors")
    def get_ease_factors(self, cards: list[int]) -> list[int]:
        """Return the ease factor (permille) of each card."""
        return [self.state.cards[c].factor for c in cards]

    def _set_queue(self, cards: list[int], *, suspend: bool) -> bool:
        changed = False
        for cid in cards:
            card = self.state.cards.get(cid)
            if card is None:
                continue
            new_queue = -1 if suspend else card.type
            if card.queue != new_queue:
                card.queue = new_queue
                card.mod = self.state.clock()
                changed = True
        return changed

    @action("suspend")
    def suspend(self, cards: list[int]) -> bool:
        """Suspend cards; True if any changed."""
        return self._set_queue(cards, suspend=True)

    @action("unsuspend")
    def unsuspend(self, cards: list[int]) -> bool:
        """Unsuspend cards; True if any changed."""
        return self._set_queue(cards, suspend=False)

    @action("suspended")
    def suspended(self, card: int) -> bool:
        """Return whether one card is suspended."""
        return self.state.cards[card].queue == -1

    @action("areSuspended")
    def are_suspended(self, cards: list[int]) -> list[bool | None]:
        """Return suspension per card; unknown ids yield None."""
        return [
            self.state.cards[c].queue == -1 if c in self.state.cards else None
            for c in cards
        ]

    @action("areDue")
    def are_due(self, cards: list[int]) -> list[bool]:
        """Return whether each card is due today or overdue."""
        return [
            self.state.cards[c].queue in (2, 3) and self.state.cards[c].due <= 0
            for c in cards
        ]

    @action("setSpecificValueOfCard")
    def set_specific_value_of_card(
        self,
        card: int,
        keys: list[str],
        newValues: list[Any],
    ) -> list[bool]:
        """Set raw card columns; supports flags, due, ivl, type, queue, reps, lapses, factor."""
        names = {"ivl": "interval"}
        target = self.state.cards[card]
        out: list[bool] = []
        for key, value in zip(keys, newValues, strict=True):
            attr = names.get(key, key)
            if attr in (
                "flags",
                "due",
                "interval",
                "type",
                "queue",
                "reps",
                "lapses",
                "factor",
            ):
                setattr(target, attr, int(value))
                out.append(True)
            else:
                out.append(False)
        target.mod = self.state.clock()
        return out

    # --- media ----------------------------------------------------------------

    @action("storeMediaFile")
    def store_media_file(
        self,
        filename: str,
        data: str | None = None,
        deleteExisting: bool = True,
        **_: Any,
    ) -> str:
        """Store base64 data under filename; return the stored name."""
        if data is None:
            raise Exception('You must provide a "data", "path", or "url" field.')
        base64.b64decode(data, validate=True)
        name = filename
        if not deleteExisting and name in self.state.media:
            stem, dot, ext = filename.rpartition(".")
            stem, ext = (stem, f".{ext}") if dot else (filename, "")
            n = 1
            while (name := f"{stem}-{n}{ext}") in self.state.media:
                n += 1
        self.state.media[name] = data
        return name

    @action("retrieveMediaFile")
    def retrieve_media_file(self, filename: str) -> str | bool:
        """Return base64 data, or False if missing."""
        return self.state.media.get(filename, False)

    @action("getMediaFilesNames")
    def get_media_files_names(self, pattern: str = "*") -> list[str]:
        """Return media names matching a glob."""
        rx = search.glob_regex(pattern, anchored=True)
        return sorted(n for n in self.state.media if rx.match(n))

    @action("deleteMediaFile")
    def delete_media_file(self, filename: str) -> None:
        """Delete a media file if present."""
        self.state.media.pop(filename, None)


def _cloze(text: str, n: int, reveal: bool) -> str:
    """Render cloze ``n`` hidden (``[...]``/hint) or revealed; others as plain text."""

    def sub(m: re.Match[str]) -> str:
        num, body, hint = int(m.group(1)), m.group(2), m.group(3)
        if num != n:
            return body
        if reveal:
            return f'<span class="cloze">{body}</span>'
        return f'<span class="cloze">[{hint or "..."}]</span>'

    return re.sub(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", sub, text)


__all__ = ["FakeAnki", "Fault", "supported_actions"]
