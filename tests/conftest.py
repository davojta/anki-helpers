"""Shared pytest fixtures."""

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run each test in an empty cwd with no API_KEY / ANKI_CONNECT_URL set."""
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ):
        os.environ.pop("API_KEY", None)
        os.environ.pop("ANKI_CONNECT_URL", None)
        yield


@pytest.fixture
def mock_anki() -> Iterator[MagicMock]:
    """Patch ``anki_helpers.cli.AnkiConnect`` and yield the client instance mock."""
    with patch("anki_helpers.cli.AnkiConnect") as mock_cls:
        yield mock_cls.return_value
