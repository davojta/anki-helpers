"""Unit tests for the CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from anki_helpers.anki_connect import AnkiConnectError
from anki_helpers.cli import cli

CARDS = [{"noteFields": {"Front": {"value": f"test word {i}"}}} for i in (1, 2, 3)]


def _fake_openai() -> MagicMock:
    """Build a MagicMock standing in for the OpenAI class."""
    openai_cls = MagicMock()
    create = openai_cls.return_value.chat.completions.create
    create.return_value.choices = [MagicMock()]
    create.return_value.choices[0].message.content = "mock response"
    return openai_cls


def test_version() -> None:
    """The version command prints the version."""
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "Anki Helpers version" in result.output


def test_hello_world() -> None:
    """The hello-world command prints a greeting."""
    result = CliRunner().invoke(cli, ["hello-world"])
    assert result.exit_code == 0
    assert "Hello World!" in result.output


def test_list_deck_sorted(mock_anki: MagicMock) -> None:
    """Decks are printed sorted."""
    mock_anki.get_deck_names.return_value = ["B", "A"]
    result = CliRunner().invoke(cli, ["list-deck"])
    assert result.exit_code == 0
    assert result.output == "Available decks:\n  • A\n  • B\n"


def test_list_deck_empty(mock_anki: MagicMock) -> None:
    """An empty deck list prints a notice."""
    mock_anki.get_deck_names.return_value = []
    result = CliRunner().invoke(cli, ["list-deck"])
    assert result.exit_code == 0
    assert "No decks found." in result.output


def test_list_deck_connection_error(mock_anki: MagicMock) -> None:
    """A connection error prints the error and a hint."""
    mock_anki.get_deck_names.side_effect = AnkiConnectError("Failed to connect")
    result = CliRunner().invoke(cli, ["list-deck"])
    assert result.exit_code == 0
    assert "Error: Failed to connect" in result.output
    assert "Make sure Anki is running" in result.output


def test_get_examples_requires_api_key(mock_anki: MagicMock, tmp_path: Path) -> None:
    """Without API_KEY the command reports an error and does nothing."""
    out = tmp_path / "out"
    result = CliRunner().invoke(cli, ["get-examples-for-red-flags-cards", str(out)])
    assert result.exit_code == 0
    assert "API_KEY not found" in result.output
    mock_anki.find_cards_with_red_flag_sorted.assert_not_called()


def test_get_examples_for_red_flags_cards(mock_anki: MagicMock, tmp_path: Path) -> None:
    """Without a limit all cards are written and OpenAI results are saved."""
    mock_anki.find_cards_with_red_flag_sorted.return_value = CARDS
    out = tmp_path / "out"
    with (
        patch("anki_helpers.cli.OpenAI", _fake_openai()),
        patch.dict("os.environ", {"API_KEY": "test_api_key"}),
    ):
        result = CliRunner().invoke(cli, ["get-examples-for-red-flags-cards", str(out)])

    assert result.exit_code == 0
    content = (out / "input-words.md").read_text()
    assert content == "test word 1\ntest word 2\ntest word 3"
    assert (out / "results.md").read_text() == "mock response"


def test_get_examples_for_red_flags_cards_limit(
    mock_anki: MagicMock, tmp_path: Path
) -> None:
    """The --limit option restricts the number of words."""
    mock_anki.find_cards_with_red_flag_sorted.return_value = CARDS
    out = tmp_path / "out"
    with (
        patch("anki_helpers.cli.OpenAI", _fake_openai()),
        patch.dict("os.environ", {"API_KEY": "test_api_key"}),
    ):
        result = CliRunner().invoke(
            cli, ["get-examples-for-red-flags-cards", "--limit", "2", str(out)]
        )

    assert result.exit_code == 0
    content = (out / "input-words.md").read_text()
    assert "test word 2" in content
    assert "test word 3" not in content
