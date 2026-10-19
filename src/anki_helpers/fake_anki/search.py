"""A subset of the Anki search syntax, evaluated against the fake state.

Supported: implicit AND, ``and``, ``or``, ``-`` negation, parentheses, quotes,
bare text (substring over all fields, ``*`` and ``_`` wildcards), ``field:value``,
``deck:``, ``tag:``, ``note:``, ``card:``, ``nid:``, ``cid:``, ``flag:``,
``is:new|learn|review|due|suspended|buried``,
``prop:due|ivl|reps|lapses|ease`` with ``= != < <= > >=``, ``edited:N``.
Anything else raises ``SearchError``.
"""

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass

from .state import (
    QUEUE_REVIEW,
    QUEUE_SUSPENDED,
    TYPE_LEARN,
    TYPE_NEW,
    Card,
    Note,
    State,
)

QUEUE_DAY_LEARN = 3
TYPE_RELEARN = 3


class SearchError(Exception):
    """The query uses syntax the fake does not understand."""


@dataclass
class Ctx:
    """What a predicate sees: one card and its note."""

    state: State
    note: Note
    card: Card


Pred = Callable[[Ctx], bool]

_OPS: dict[str, Callable[[float, float], bool]] = {
    "<=": operator.le,
    ">=": operator.ge,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
    "=": operator.eq,
}


def tokenize(query: str) -> list[str]:
    """Split a query into terms, ``(``, ``)``; quotes group and are removed."""
    tokens: list[str] = []
    buf = ""
    quoted = False  # buf contains a quoted part, so keep it even if empty
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == '"':
            end = query.find('"', i + 1)
            if end == -1:
                raise SearchError("unterminated quote")
            buf += query[i + 1 : end]
            quoted = True
            i = end + 1
            continue
        if ch.isspace() or ch in "()":
            if buf or quoted:
                tokens.append(buf)
            buf, quoted = "", False
            if ch in "()":
                tokens.append(ch)
        else:
            buf += ch
        i += 1
    if buf or quoted:
        tokens.append(buf)
    return tokens


def glob_regex(pattern: str, *, anchored: bool) -> re.Pattern[str]:
    r"""Anki wildcards: ``*`` any run, ``_`` one char; ``\*``/``\_`` literal."""
    out = ""
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            out += re.escape(pattern[i + 1])
            i += 2
            continue
        out += ".*" if ch == "*" else "." if ch == "_" else re.escape(ch)
        i += 1
    if anchored:
        out = f"^{out}$"
    return re.compile(out, re.IGNORECASE | re.DOTALL)


def _ids(value: str) -> set[int]:
    try:
        return {int(v) for v in value.split(",") if v}
    except ValueError as e:
        raise SearchError(f"invalid id list: {value}") from e


def _deck_pred(value: str) -> Pred:
    """``deck:X`` matches X and its subdecks."""
    rx = glob_regex(value, anchored=True)

    def pred(c: Ctx) -> bool:
        parts = c.card.deck.split("::")
        return any(rx.match("::".join(parts[:i])) for i in range(1, len(parts) + 1))

    return pred


def _tag_pred(value: str) -> Pred:
    """``tag:X`` matches X and child tags ``X::*``; ``tag:none`` untagged."""
    if value.lower() == "none":
        return lambda c: not c.note.tags
    rx = glob_regex(value, anchored=True)
    child = glob_regex(value + "::*", anchored=True)
    return lambda c: any(rx.match(t) or child.match(t) for t in c.note.tags)


def _is_pred(value: str) -> Pred:
    preds: dict[str, Pred] = {
        "new": lambda c: c.card.type == TYPE_NEW,
        "learn": lambda c: c.card.type in (TYPE_LEARN, TYPE_RELEARN),
        "review": lambda c: c.card.type in (2, TYPE_RELEARN),
        "due": lambda c: (
            c.card.queue in (QUEUE_REVIEW, QUEUE_DAY_LEARN) and c.card.due <= 0
        ),
        "suspended": lambda c: c.card.queue == QUEUE_SUSPENDED,
        "buried": lambda c: c.card.queue in (-2, -3),
    }
    try:
        return preds[value.lower()]
    except KeyError:
        raise SearchError(f"unsupported is:{value}") from None


def _prop_pred(value: str) -> Pred:
    m = re.fullmatch(r"(\w+)(<=|>=|!=|<|>|=)(-?\d+(?:\.\d+)?)", value)
    if not m:
        raise SearchError(f"invalid prop:{value}")
    name, op, num = m.group(1).lower(), _OPS[m.group(2)], float(m.group(3))
    getters: dict[str, Callable[[Card], float]] = {
        "ivl": lambda card: card.interval,
        "reps": lambda card: card.reps,
        "lapses": lambda card: card.lapses,
        "ease": lambda card: card.factor / 1000,
    }
    if name == "due":
        # Like Anki: only cards in a day-based review queue have a due day.
        return lambda c: (
            c.card.queue in (QUEUE_REVIEW, QUEUE_DAY_LEARN) and op(c.card.due, num)
        )
    if name not in getters:
        raise SearchError(f"unsupported prop:{name}")
    get = getters[name]
    if name == "ease":
        # New cards have no ease yet (factor 0); Anki skips them.
        return lambda c: c.card.type != TYPE_NEW and op(get(c.card), num)
    return lambda c: op(get(c.card), num)


def _card_pred(value: str) -> Pred:
    if value.isdigit():
        n = int(value) - 1
        return lambda c: c.card.ord == n
    rx = glob_regex(value, anchored=True)

    def pred(c: Ctx) -> bool:
        templates = c.state.models[c.note.model].templates
        if c.state.models[c.note.model].is_cloze:
            return False
        return c.card.ord < len(templates) and bool(
            rx.match(templates[c.card.ord].name)
        )

    return pred


def _field_pred(name: str, value: str) -> Pred:
    name_rx = glob_regex(name, anchored=True)
    rx = glob_regex(value, anchored=True)
    return lambda c: any(
        name_rx.match(k) and rx.match(v) for k, v in c.note.fields.items()
    )


def _text_pred(value: str) -> Pred:
    rx = glob_regex(value, anchored=False)
    return lambda c: any(rx.search(v) for v in c.note.fields.values())


def term(token: str) -> Pred:
    """Compile one search term (no operators) to a predicate."""
    key, sep, value = token.partition(":")
    if not sep or not key:
        return _text_pred(token)
    key = key.lower()
    match key:
        case "deck":
            return _deck_pred(value)
        case "tag":
            return _tag_pred(value)
        case "note":
            rx = glob_regex(value, anchored=True)
            return lambda c: bool(rx.match(c.note.model))
        case "card":
            return _card_pred(value)
        case "nid":
            ids = _ids(value)
            return lambda c: c.note.id in ids
        case "cid":
            ids = _ids(value)
            return lambda c: c.card.id in ids
        case "flag":
            if not value.isdigit():
                raise SearchError(f"invalid flag:{value}")
            n = int(value)
            return lambda c: (c.card.flags & 0b111) == n
        case "is":
            return _is_pred(value)
        case "prop":
            return _prop_pred(value)
        case "edited":
            if not value.isdigit():
                raise SearchError(f"invalid edited:{value}")
            days = int(value)
            return lambda c: c.note.mod > c.state.clock() - days * 86_400
        case (
            "added" | "rated" | "introduced" | "re" | "nc" | "w" | "dupe"
            | "preset" | "has-cd" | "resched"
        ):  # fmt: skip
            raise SearchError(f"unsupported search: {token}")
        case _:
            return _field_pred(key, value)


class _Parser:
    """Recursive descent: or_expr := and_expr ('or' and_expr)*."""

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> Pred:
        if not self.tokens:
            return lambda c: True
        pred = self.or_expr()
        if self.peek() is not None:
            raise SearchError(f"unexpected {self.peek()!r}")
        return pred

    def or_expr(self) -> Pred:
        preds = [self.and_expr()]
        while (tok := self.peek()) is not None and tok.lower() == "or":
            self.take()
            preds.append(self.and_expr())
        if len(preds) == 1:
            return preds[0]
        return lambda c: any(p(c) for p in preds)

    def and_expr(self) -> Pred:
        preds = [self.unary()]
        while (tok := self.peek()) is not None and tok != ")" and tok.lower() != "or":
            if tok.lower() == "and":
                self.take()
            preds.append(self.unary())
        if len(preds) == 1:
            return preds[0]
        return lambda c: all(p(c) for p in preds)

    def unary(self) -> Pred:
        tok = self.peek()
        if tok is None or tok == ")" or tok.lower() in ("and", "or"):
            raise SearchError(f"expected a search term, got {tok!r}")
        self.take()
        if tok == "(":
            inner = self.or_expr()
            if self.peek() != ")":
                raise SearchError("missing ')'")
            self.take()
            return inner
        if tok == "-":
            negated = self.unary()
            return lambda c: not negated(c)
        if tok.startswith("-") and len(tok) > 1:
            negated = term(tok[1:])
            return lambda c: not negated(c)
        return term(tok)


def compile_query(query: str) -> Pred:
    """Compile a full search string to a card-level predicate."""
    return _Parser(tokenize(query)).parse()


def find_cards(state: State, query: str) -> list[int]:
    """Return ids of cards matching query, in id order."""
    pred = compile_query(query)
    return [
        card.id
        for card in sorted(state.cards.values(), key=lambda c: c.id)
        if pred(Ctx(state, state.notes[card.note_id], card))
    ]


def find_notes(state: State, query: str) -> list[int]:
    """Return ids of notes with at least one matching card, in id order."""
    pred = compile_query(query)
    return sorted(
        {
            card.note_id
            for card in state.cards.values()
            if pred(Ctx(state, state.notes[card.note_id], card))
        }
    )
