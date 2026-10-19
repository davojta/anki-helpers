"""Unit tests for the AnkiConnect client."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner

from anki_helpers.anki_connect import DEFAULT_URL, AnkiConnect, AnkiConnectError
from anki_helpers.cli import cli


def _response(payload: dict[str, object]) -> MagicMock:
    """Build a fake requests response returning payload."""
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


def test_invoke_returns_result() -> None:
    """The result field is returned and the request body is well-formed."""
    with patch(
        "requests.post", return_value=_response({"result": ["A"], "error": None})
    ) as post:
        assert AnkiConnect().get_deck_names() == ["A"]
    assert post.call_args.kwargs["json"] == {
        "action": "deckNames",
        "version": 6,
        "params": {},
    }


def test_error_field_raises() -> None:
    """A non-null error field raises AnkiConnectError."""
    with (
        patch(
            "requests.post", return_value=_response({"result": None, "error": "boom"})
        ),
        pytest.raises(AnkiConnectError) as exc_info,
    ):
        AnkiConnect().get_deck_names()
    assert str(exc_info.value) == "AnkiConnect error: boom"


def test_network_failure_raises_with_cause() -> None:
    """A RequestException is wrapped and kept as __cause__."""
    err = requests.ConnectionError("refused")
    with (
        patch("requests.post", side_effect=err),
        pytest.raises(AnkiConnectError) as exc_info,
    ):
        AnkiConnect().get_deck_names()
    assert "Failed to connect to AnkiConnect" in str(exc_info.value)
    assert exc_info.value.__cause__ is err


def test_url_arg_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit argument beats the environment."""
    monkeypatch.setenv("ANKI_CONNECT_URL", "http://env:1")
    assert AnkiConnect("http://arg:2").url == "http://arg:2"


def test_url_from_shell_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """ANKI_CONNECT_URL from the environment is used."""
    monkeypatch.setenv("ANKI_CONNECT_URL", "http://env:1")
    assert AnkiConnect().url == "http://env:1"


def test_url_from_dotenv(tmp_path: Path) -> None:
    """A .env in cwd is loaded by the cli group and used."""
    (tmp_path / ".env").write_text('ANKI_CONNECT_URL="http://dotenv:3"\n')
    CliRunner().invoke(cli, ["version"])
    assert AnkiConnect().url == "http://dotenv:3"


def test_shell_env_beats_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """.env never overrides an existing environment variable."""
    (tmp_path / ".env").write_text("ANKI_CONNECT_URL=http://dotenv:3\n")
    monkeypatch.setenv("ANKI_CONNECT_URL", "http://env:1")
    CliRunner().invoke(cli, ["version"])
    assert AnkiConnect().url == "http://env:1"


def test_default_url() -> None:
    """With nothing set the default URL is used."""
    assert AnkiConnect().url == DEFAULT_URL == "http://localhost:8765"
