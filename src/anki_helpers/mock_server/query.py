"""Tiny parser for the subset of Anki's search DSL used by this project.

The supported grammar (whitespace-separated, AND by default):

* ``deck:Name``           -- note/card belongs to deck ``Name`` or a subdeck
* ``tag:Name``            -- note has tag ``Name`` or a subtag (``Name::sub``)
* ``flag:N``              -- some card on the note has the flag value ``N``
* ``nid:1,2,3``           -- note id is in the list
* ``cid:1,2,3``           -- card id is in the list
* ``prop:due<N`` etc.     -- cards' ``due`` (or ``ivl``/``reps``/``lapses``)
                             matches the integer comparison
* ``is:suspended``        -- some card on the note is suspended
* ``is:new``              -- some card on the note has reps == 0
* ``is:due``              -- some card on the note has due <= 0
* ``<field>:value``       -- the note's field equals ``value`` (``*`` glob ok)
* bare text               -- substring match on any field value
* ``-token``              -- negation of any of the above

Unknown predicates raise ``ValueError`` so missing coverage is loud rather
than silently returning empty results.
"""

import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence

CARD_NUMERIC_PROPS = {"due", "ivl", "reps", "lapses", "factor"}
COMPARATORS: Dict[str, Callable[[int, int], bool]] = {
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "=": lambda a, b: a == b,
}
COMPARATOR_RE = re.compile(r"^(?P<key>[a-zA-Z]+)(?P<op><=|>=|!=|<|>|=)(?P<val>-?\d+)$")


@dataclass
class Token:
    """One parsed predicate from the search query."""

    kind: str
    value: Any = None
    negated: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteCtx:
    """Bundle of data needed to evaluate predicates against a note."""

    note: Dict[str, Any]
    cards: List[Dict[str, Any]]


@dataclass
class CardCtx:
    """Bundle of data needed to evaluate predicates against a card."""

    card: Dict[str, Any]
    note: Dict[str, Any]


def parse_query(query: str) -> List[Token]:
    """Tokenize a raw query string into a list of :class:`Token`.

    Args:
        query: The Anki-style search string.

    Returns:
        A list of :class:`Token` objects ready for matching.

    Raises:
        ValueError: If the query contains an operator the mock does not
            recognize (e.g. ``re:`` regex search).
    """
    if not query or not query.strip():
        return []
    raw_tokens = shlex.split(query)
    out: List[Token] = []
    for raw in raw_tokens:
        negated = raw.startswith("-")
        body = raw[1:] if negated else raw
        if not body:
            continue
        token = _classify(body)
        token.negated = negated
        out.append(token)
    return out


def _classify(body: str) -> Token:
    """Classify a single non-empty token body.

    Args:
        body: Token text without the leading negation marker.

    Returns:
        A :class:`Token` describing the predicate.

    Raises:
        ValueError: If the predicate is not supported.
    """
    if ":" not in body:
        return Token(kind="bare", value=body)
    key, _, value = body.partition(":")
    key_lower = key.lower()
    if key_lower == "deck":
        return Token(kind="deck", value=value)
    if key_lower == "tag":
        return Token(kind="tag", value=value)
    if key_lower == "flag":
        return Token(kind="flag", value=_parse_int(value, "flag"))
    if key_lower == "nid":
        return Token(kind="nid", value=_parse_id_list(value))
    if key_lower == "cid":
        return Token(kind="cid", value=_parse_id_list(value))
    if key_lower == "is":
        if value not in {"suspended", "new", "due"}:
            raise ValueError(f"unsupported is: predicate: {value}")
        return Token(kind="is", value=value)
    if key_lower == "prop":
        match = COMPARATOR_RE.match(value)
        if not match:
            raise ValueError(f"unsupported prop: predicate: {value}")
        prop_key = match["key"].lower()
        if prop_key not in CARD_NUMERIC_PROPS:
            raise ValueError(f"unsupported prop:{prop_key}")
        return Token(
            kind="prop",
            value=int(match["val"]),
            extra={"prop": prop_key, "op": match["op"]},
        )
    return Token(kind="field", value=value, extra={"name": key})


def _parse_int(raw: str, label: str) -> int:
    """Parse an integer from text, raising a labelled error on failure."""
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid integer for {label}: {raw}") from exc


def _parse_id_list(raw: str) -> List[int]:
    """Parse a ``1,2,3`` style comma-separated id list."""
    out: List[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        out.append(_parse_int(piece, "id list"))
    return out


def match_note(tokens: Sequence[Token], ctx: NoteCtx) -> bool:
    """Return ``True`` when every (non-negated) token matches the note.

    Args:
        tokens: Parsed query tokens.
        ctx: Note plus its card list.

    Returns:
        Whether the note satisfies every predicate.
    """
    return all(_apply(t, ctx) for t in tokens)


def match_card(tokens: Sequence[Token], ctx: CardCtx) -> bool:
    """Return ``True`` when every (non-negated) token matches the card.

    Args:
        tokens: Parsed query tokens.
        ctx: Card plus the owning note.

    Returns:
        Whether the card satisfies every predicate.
    """
    return all(_apply(t, ctx) for t in tokens)


def _apply(token: Token, ctx: Any) -> bool:
    """Evaluate a single token, accounting for its negation flag."""
    matched = _evaluate(token, ctx)
    return not matched if token.negated else matched


def _evaluate(token: Token, ctx: Any) -> bool:
    """Dispatch a token to the appropriate matching helper."""
    if isinstance(ctx, NoteCtx):
        return _evaluate_note(token, ctx)
    if isinstance(ctx, CardCtx):
        return _evaluate_card(token, ctx)
    raise TypeError(f"unsupported context type: {type(ctx)!r}")


def _evaluate_note(token: Token, ctx: NoteCtx) -> bool:
    """Evaluate a token against a note context."""
    note = ctx.note
    cards = ctx.cards
    if token.kind == "deck":
        return _deck_matches(token.value, note["deck_name"])
    if token.kind == "tag":
        tags = json.loads(note["tags_json"])
        return any(_tag_matches(token.value, t) for t in tags)
    if token.kind == "flag":
        return any(card["flags"] == token.value for card in cards)
    if token.kind == "nid":
        return note["id"] in token.value
    if token.kind == "cid":
        return any(card["id"] in token.value for card in cards)
    if token.kind == "is":
        return any(_is_matches(token.value, card) for card in cards)
    if token.kind == "prop":
        op = COMPARATORS[token.extra["op"]]
        prop = token.extra["prop"]
        return any(op(int(card[prop]), int(token.value)) for card in cards)
    if token.kind == "field":
        return _field_matches(token, json.loads(note["fields_json"]))
    if token.kind == "bare":
        fields = json.loads(note["fields_json"])
        needle = token.value.lower()
        return any(needle in (v or "").lower() for v in fields.values())
    raise ValueError(f"unknown token kind: {token.kind}")


def _evaluate_card(token: Token, ctx: CardCtx) -> bool:
    """Evaluate a token against a card context."""
    card = ctx.card
    note = ctx.note
    if token.kind == "deck":
        return _deck_matches(token.value, card["deck_name"])
    if token.kind == "tag":
        tags = json.loads(note["tags_json"])
        return any(_tag_matches(token.value, t) for t in tags)
    if token.kind == "flag":
        return card["flags"] == token.value
    if token.kind == "nid":
        return note["id"] in token.value
    if token.kind == "cid":
        return card["id"] in token.value
    if token.kind == "is":
        return _is_matches(token.value, card)
    if token.kind == "prop":
        op = COMPARATORS[token.extra["op"]]
        prop = token.extra["prop"]
        return op(int(card[prop]), int(token.value))
    if token.kind == "field":
        return _field_matches(token, json.loads(note["fields_json"]))
    if token.kind == "bare":
        fields = json.loads(note["fields_json"])
        needle = token.value.lower()
        return any(needle in (v or "").lower() for v in fields.values())
    raise ValueError(f"unknown token kind: {token.kind}")


def _deck_matches(query_deck: str, actual_deck: str) -> bool:
    """Match deck queries, including subdecks (``Foo`` matches ``Foo::Bar``)."""
    return actual_deck == query_deck or actual_deck.startswith(query_deck + "::")


def _tag_matches(query_tag: str, actual_tag: str) -> bool:
    """Match tag queries, including subtags (``foo`` matches ``foo::bar``)."""
    return actual_tag == query_tag or actual_tag.startswith(query_tag + "::")


def _is_matches(value: str, card: Dict[str, Any]) -> bool:
    """Evaluate the ``is:...`` predicate family for one card."""
    if value == "suspended":
        return bool(card["suspended"])
    if value == "new":
        return int(card["reps"]) == 0
    if value == "due":
        return int(card["due"]) <= 0
    return False


def _field_matches(token: Token, fields: Dict[str, str]) -> bool:
    """Match ``<field>:value``, with case-insensitive name + ``*`` glob."""
    name_lc = token.extra["name"].lower()
    value: str = token.value
    target = next(
        (k for k in fields if k.lower() == name_lc),
        None,
    )
    if target is None:
        return False
    actual = fields.get(target, "") or ""
    if "*" in value:
        regex = re.compile(
            "^" + re.escape(value).replace("\\*", ".*") + "$",
            re.IGNORECASE,
        )
        return regex.match(actual) is not None
    return actual == value
