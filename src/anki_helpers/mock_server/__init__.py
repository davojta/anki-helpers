"""Stateful mock server for AnkiConnect.

This package provides a minimal, SQLite-backed, drop-in replacement for the
AnkiConnect HTTP plugin. It is intended for local development and CI tests
where running a full Anki instance is impractical.
"""

from .server import MockAnkiConnectServer, run_server
from .state import State

__all__ = ["MockAnkiConnectServer", "State", "run_server"]
