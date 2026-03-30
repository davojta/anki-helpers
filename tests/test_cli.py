"""Tests for the CLI module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from anki_helpers.cli import cli


def _make_openai_mock(mocker):
    """Create and register a mock OpenAI client."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a mock response from OpenAI API."

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mocker.patch("anki_helpers.cli.OpenAI", return_value=mock_client)
    return mock_client


def test_version():
    """Test the version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "Anki Helpers version" in result.output


def test_get_examples_for_red_flags_cards(mocker):
    """Test the get_examples_for_red_flags_cards command."""
    mock_anki = MagicMock()
    mock_anki.find_cards_with_red_flag_sorted.return_value = [
        {"noteFields": {"Front": {"value": "test word 1"}}},
        {"noteFields": {"Front": {"value": "test word 2"}}},
        {"noteFields": {"Front": {"value": "test word 3"}}},
    ]
    mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)
    _make_openai_mock(mocker)
    mocker.patch.dict("os.environ", {"API_KEY": "test_api_key"})

    # Test without limit
    with tempfile.TemporaryDirectory() as temp_dir:
        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", temp_dir])

        assert result.exit_code == 0

        input_file_path = Path(temp_dir) / "input-words.md"
        assert input_file_path.exists()

        results_file_path = Path(temp_dir) / "results.md"
        assert results_file_path.exists()

        with open(input_file_path) as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" in content

    # Test with limit
    with tempfile.TemporaryDirectory() as temp_dir:
        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", "--limit", "2", temp_dir])

        assert result.exit_code == 0

        input_file_path = Path(temp_dir) / "input-words.md"
        assert input_file_path.exists()

        with open(input_file_path) as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" not in content

    assert mock_anki.find_cards_with_red_flag_sorted.call_count == 2
