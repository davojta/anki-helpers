"""In-memory Anki collection used by the fake AnkiConnect."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

Clock = Callable[[], int]

FIRST_ID = 1_700_000_000_000
DEFAULT_TODAY = 20_000

# Card type / queue values as in Anki.
TYPE_NEW, TYPE_LEARN, TYPE_REVIEW = 0, 1, 2
QUEUE_SUSPENDED, QUEUE_NEW, QUEUE_REVIEW = -1, 0, 2

DEFAULT_CSS = ".card {\n font-family: arial;\n font-size: 20px;\n}\n"


@dataclass
class Template:
    """A card template of a note type."""

    name: str
    front: str
    back: str


@dataclass
class Model:
    """A note type."""

    id: int
    name: str
    fields: list[str]
    templates: list[Template]
    css: str = DEFAULT_CSS
    is_cloze: bool = False


@dataclass
class Note:
    """An Anki note. ``fields`` keeps the model's field order."""

    id: int
    model: str
    fields: dict[str, str]
    tags: list[str]
    mod: int


@dataclass
class Card:
    """An Anki card.

    ``due`` is days relative to ``State.today`` for review cards (0 = today,
    negative = overdue) and the queue position for new cards.
    """

    id: int
    note_id: int
    deck: str
    ord: int
    mod: int
    type: int = TYPE_NEW
    queue: int = QUEUE_NEW
    due: int = 0
    interval: int = 0
    factor: int = 0
    reps: int = 0
    lapses: int = 0
    flags: int = 0


def stock_models() -> list[Model]:
    """Return the note types every new collection has."""
    return [
        Model(
            id=1,
            name="Basic",
            fields=["Front", "Back"],
            templates=[
                Template("Card 1", "{{Front}}", "{{FrontSide}}<hr id=answer>{{Back}}")
            ],
        ),
        Model(
            id=2,
            name="Basic (and reversed card)",
            fields=["Front", "Back"],
            templates=[
                Template("Card 1", "{{Front}}", "{{FrontSide}}<hr id=answer>{{Back}}"),
                Template("Card 2", "{{Back}}", "{{FrontSide}}<hr id=answer>{{Front}}"),
            ],
        ),
        Model(
            id=3,
            name="Cloze",
            fields=["Text", "Back Extra"],
            templates=[
                Template("Cloze", "{{cloze:Text}}", "{{cloze:Text}}<br>{{Back Extra}}")
            ],
            is_cloze=True,
        ),
    ]


def system_clock() -> int:
    """Return the current Unix time in seconds."""
    return int(time.time())


@dataclass
class State:
    """The whole fake collection. Mutated only by ``FakeAnki`` actions."""

    clock: Clock = system_clock
    today: int = DEFAULT_TODAY
    decks: dict[str, int] = field(default_factory=lambda: {"Default": 1})
    models: dict[str, Model] = field(
        default_factory=lambda: {m.name: m for m in stock_models()}
    )
    notes: dict[int, Note] = field(default_factory=dict[int, Note])
    cards: dict[int, Card] = field(default_factory=dict[int, Card])
    media: dict[str, str] = field(default_factory=dict[str, str])
    next_id: int = FIRST_ID

    def new_id(self) -> int:
        """Return a fresh, increasing id for decks, notes and cards."""
        self.next_id += 1
        return self.next_id

    def ensure_deck(self, name: str) -> int:
        """Create ``name`` and its parents if missing; return its id."""
        parts = name.split("::")
        for i in range(1, len(parts) + 1):
            self.decks.setdefault("::".join(parts[:i]), self.new_id())
        return self.decks[name]

    def cards_of(self, note_id: int) -> list[Card]:
        """Return the cards of a note, ordered by ``ord``."""
        return sorted(
            (c for c in self.cards.values() if c.note_id == note_id),
            key=lambda c: c.ord,
        )

    def card_ords(self, note: Note) -> list[int]:
        """Return the template ords a note should have cards for."""
        model = self.models[note.model]
        if model.is_cloze:
            return [n - 1 for n in cloze_numbers(next(iter(note.fields.values())))]
        return [
            i
            for i, t in enumerate(model.templates)
            if any(note.fields.get(f) for f in _template_fields(t.front))
        ]


def cloze_numbers(text: str) -> list[int]:
    """Return the sorted cloze numbers (``{{c1::...}}`` → 1) used in text."""
    return sorted({int(n) for n in re.findall(r"\{\{c(\d+)::", text)})


def _template_fields(fmt: str) -> list[str]:
    return [m.split(":")[-1] for m in re.findall(r"\{\{([^}#/^]+)\}\}", fmt)]


# --- seed / dump --------------------------------------------------------------


def load_state(data: dict[str, Any], clock: Clock = system_clock) -> State:
    """Build a state from a seed dict (see ``fixtures/basic.json``).

    Notes need ``deck``, ``model`` and ``fields``; ``id``, ``tags``, ``mod``
    and per-card overrides (``cards``) are
    optional. Cards not listed get defaults (new, unflagged).
    """
    state = State(clock=clock, today=int(data.get("today", DEFAULT_TODAY)))
    for raw in cast("list[dict[str, Any]]", data.get("models", [])):
        state.models[raw["name"]] = Model(
            id=int(raw.get("id") or state.new_id()),
            name=raw["name"],
            fields=list(raw["fields"]),
            templates=[
                Template(t["name"], t["front"], t["back"])
                for t in cast("list[dict[str, str]]", raw["templates"])
            ],
            css=raw.get("css", DEFAULT_CSS),
            is_cloze=bool(raw.get("isCloze", False)),
        )
    for name in cast("list[str]", data.get("decks", [])):
        state.ensure_deck(name)
    raw_notes = cast("list[dict[str, Any]]", data.get("notes", []))
    ids = [int(n["id"]) for n in raw_notes if "id" in n]
    ids += [int(c["id"]) for n in raw_notes for c in n.get("cards", []) if "id" in c]
    state.next_id = max([state.next_id, *ids])
    now = clock()
    for raw in raw_notes:
        model = state.models[raw["model"]]
        fields = {f: str(raw["fields"].get(f, "")) for f in model.fields}
        note = Note(
            id=int(raw.get("id") or state.new_id()),
            model=model.name,
            fields=fields,
            tags=list(raw.get("tags", [])),
            mod=int(raw.get("mod", now)),
        )
        state.notes[note.id] = note
        state.ensure_deck(raw["deck"])
        overrides = cast("list[dict[str, Any]]", raw.get("cards", []))
        # Overrides with "ord" (as dumped) pin the exact cards, so cards kept
        # after a field edit survive a round trip; else they go by position.
        if overrides and all("ord" in o for o in overrides):
            pairs = [(int(o["ord"]), o) for o in overrides]
        else:
            ords = state.card_ords(note)
            pairs = [
                (ord_, overrides[pos] if pos < len(overrides) else {})
                for pos, ord_ in enumerate(ords)
            ]
        for ord_, extra in pairs:
            card = Card(
                id=int(extra.get("id") or state.new_id()),
                note_id=note.id,
                deck=str(extra.get("deck", raw["deck"])),
                ord=ord_,
                mod=int(extra.get("mod", note.mod)),
            )
            for key in ("type", "queue", "due", "interval", "factor", "reps"):
                if key in extra:
                    setattr(card, key, int(extra[key]))
            card.lapses = int(extra.get("lapses", 0))
            card.flags = int(extra.get("flags", 0))
            if "type" in extra and "queue" not in extra:
                card.queue = card.type
            state.ensure_deck(card.deck)
            state.cards[card.id] = card
    state.media.update(cast("dict[str, str]", data.get("media", {})))
    return state


def _note_deck(state: State, note_id: int) -> str:
    cards = state.cards_of(note_id)
    return cards[0].deck if cards else "Default"


def dump_state(state: State) -> dict[str, Any]:
    """Serialize a state to a seed dict that ``load_state`` reads back."""
    stock = {m.name for m in stock_models()}
    return {
        "today": state.today,
        "decks": sorted(state.decks),
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "fields": m.fields,
                "templates": [
                    {"name": t.name, "front": t.front, "back": t.back}
                    for t in m.templates
                ],
                "css": m.css,
                "isCloze": m.is_cloze,
            }
            for m in state.models.values()
            if m.name not in stock
        ],
        "notes": [
            {
                "id": n.id,
                "deck": _note_deck(state, n.id),
                "model": n.model,
                "fields": n.fields,
                "tags": n.tags,
                "mod": n.mod,
                "cards": [
                    {
                        "id": c.id,
                        "ord": c.ord,
                        "deck": c.deck,
                        "mod": c.mod,
                        "type": c.type,
                        "queue": c.queue,
                        "due": c.due,
                        "interval": c.interval,
                        "factor": c.factor,
                        "reps": c.reps,
                        "lapses": c.lapses,
                        "flags": c.flags,
                    }
                    for c in state.cards_of(n.id)
                ],
            }
            for n in state.notes.values()
        ],
        "media": state.media,
    }
