"""Fake AnkiConnect: a stateful v6 emulator for tests and manual query checks."""

import json
from importlib import resources
from typing import Any, cast

from .actions import FakeAnki, Fault, supported_actions
from .search import SearchError, compile_query
from .server import FakeServer, make_server, running
from .state import State, dump_state, load_state


def sample_seed() -> dict[str, Any]:
    """Return the bundled sample collection (``fixtures/basic.json``)."""
    text = resources.files(__package__).joinpath("fixtures/basic.json").read_text()
    return cast("dict[str, Any]", json.loads(text))


__all__ = [
    "FakeAnki",
    "FakeServer",
    "Fault",
    "SearchError",
    "State",
    "compile_query",
    "dump_state",
    "load_state",
    "make_server",
    "running",
    "sample_seed",
    "supported_actions",
]
