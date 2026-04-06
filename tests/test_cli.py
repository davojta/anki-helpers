"""Tests for the CLI module."""

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


def test_hello_world():
    """Test the hello_world command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["hello-world"])
    assert result.exit_code == 0
    assert "Hello World!" in result.output


class TestListDeck:
    """Tests for list_deck command."""

    def test_list_decks_success(self, mocker):
        """Test listing decks successfully."""
        mock_anki = MagicMock()
        mock_anki.get_deck_names.return_value = ["Default", "Finnish", "German"]
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "Available decks:" in result.output
        assert "Default" in result.output
        assert "Finnish" in result.output
        assert "German" in result.output

    def test_list_decks_empty(self, mocker):
        """Test listing decks when none exist."""
        mock_anki = MagicMock()
        mock_anki.get_deck_names.return_value = []
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "No decks found." in result.output

    def test_list_decks_error(self, mocker):
        """Test listing decks with connection error."""
        from anki_helpers.anki_connect import AnkiConnectError

        mock_anki = MagicMock()
        mock_anki.get_deck_names.side_effect = AnkiConnectError("Connection failed")
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "Error: Connection failed" in result.output
        assert "Make sure Anki is running" in result.output


class TestListRedFlags:
    """Tests for list_red_flags command."""

    def test_list_flags_success(self, mocker):
        """Test listing red flag cards successfully."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = [
            {
                "noteFields": {"Front": {"value": "kissa"}},
                "noteTags": ["finnish", "noun"],
                "dueQuery": 0,
            },
            {
                "noteFields": {"Front": {"value": "koira"}},
                "noteTags": ["finnish", "noun"],
                "dueQuery": -1,
            },
        ]
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-red-flags"])

        assert result.exit_code == 0
        assert "Cards with red flags" in result.output
        assert "kissa" in result.output
        assert "koira" in result.output
        assert "Tags:" in result.output

    def test_list_flags_empty(self, mocker):
        """Test listing flags when none exist."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = []
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-red-flags"])

        assert result.exit_code == 0
        assert "No cards with red flags found." in result.output

    def test_list_flags_with_limit(self, mocker):
        """Test listing flags with custom limit."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = [
            {
                "noteFields": {"Front": {"value": f"word{i}"}},
                "noteTags": [],
                "dueQuery": i,
            }
            for i in range(10)
        ]
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-red-flags", "--limit", "3"])

        assert result.exit_code == 0
        assert "word0" in result.output
        assert "word1" in result.output
        assert "word2" in result.output
        assert "word3" not in result.output

    def test_list_flags_html_cleaning(self, mocker):
        """Test HTML content is cleaned."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = [
            {
                "noteFields": {"Front": {"value": "<strong>kissa</strong>&nbsp;[sound:cat.mp3]"}},
                "noteTags": [],
                "dueQuery": 0,
            }
        ]
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)

        runner = CliRunner()
        result = runner.invoke(cli, ["list-red-flags"])

        assert result.exit_code == 0
        assert "kissa" in result.output
        assert "<strong>" not in result.output
        assert "[sound:" not in result.output


class TestGetExamplesForRedFlagsCards:
    """Tests for get_examples_for_red_flags_cards command."""

    def test_no_api_key(self, mocker, tmp_path):
        """Test error when API key is missing."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = []
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)
        # Patch both os.environ and the .env file loading
        mocker.patch.dict("os.environ", {}, clear=True)
        mocker.patch("anki_helpers.cli.Path", wraps=Path)
        # Make the .env file not exist by patching Path.exists to return False for .env
        original_exists = Path.exists

        def mock_exists(self):
            if str(self).endswith(".env"):
                return False
            return original_exists(self)

        mocker.patch("pathlib.Path.exists", mock_exists)

        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", str(tmp_path)])

        assert result.exit_code == 0
        assert "API_KEY not found" in result.output

    def test_no_red_flags(self, mocker, tmp_path):
        """Test when no red flag cards exist."""
        mock_anki = MagicMock()
        mock_anki.find_cards_with_red_flag_sorted.return_value = []
        mocker.patch("anki_helpers.cli.AnkiConnect", return_value=mock_anki)
        mocker.patch.dict("os.environ", {"API_KEY": "test_key"})

        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", str(tmp_path)])

        assert result.exit_code == 0
        assert "No cards with red flags found." in result.output

    def test_success(self, mocker, tmp_path):
        """Test the get_examples_for_red_flags_cards command successfully."""
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
        temp_dir = tmp_path / "no_limit"
        temp_dir.mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", str(temp_dir)])

        assert result.exit_code == 0

        input_file_path = temp_dir / "input-words.md"
        assert input_file_path.exists()

        results_file_path = temp_dir / "results.md"
        assert results_file_path.exists()

        with open(input_file_path) as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" in content

        # Test with limit
        temp_dir2 = tmp_path / "with_limit"
        temp_dir2.mkdir()
        runner = CliRunner()
        result = runner.invoke(
            cli, ["get-examples-for-red-flags-cards", "--limit", "2", str(temp_dir2)]
        )

        assert result.exit_code == 0

        input_file_path = temp_dir2 / "input-words.md"
        assert input_file_path.exists()

        with open(input_file_path) as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" not in content

        assert mock_anki.find_cards_with_red_flag_sorted.call_count == 2


class TestGenerateExamplesForWord:
    """Tests for generate_examples_for_word command."""

    def test_missing_api_key(self, mocker, tmp_path):
        """Test error when API key is missing."""
        words_file = tmp_path / "words.md"
        words_file.write_text("kissa\nkoira")
        # Patch both os.environ and the .env file loading
        mocker.patch.dict("os.environ", {}, clear=True)
        original_exists = Path.exists

        def mock_exists(self):
            if str(self).endswith(".env"):
                return False
            return original_exists(self)

        mocker.patch("pathlib.Path.exists", mock_exists)

        runner = CliRunner()
        result = runner.invoke(cli, ["generate-examples-for-word", str(words_file)])

        assert result.exit_code == 0
        assert "API_KEY not found" in result.output

    def test_empty_words_file(self, mocker, tmp_path):
        """Test error when words file is empty."""
        words_file = tmp_path / "words.md"
        words_file.write_text("   \n  \n")
        mocker.patch.dict("os.environ", {"API_KEY": "test_key"})

        runner = CliRunner()
        result = runner.invoke(cli, ["generate-examples-for-word", str(words_file)])

        assert result.exit_code == 0
        assert "Words file is empty" in result.output

    def test_generate_examples_success(self, mocker, tmp_path):
        """Test successful example generation."""
        words_file = tmp_path / "words.md"
        words_file.write_text("kissa\nkoira\n")
        _make_openai_mock(mocker)
        mocker.patch.dict("os.environ", {"API_KEY": "test_key"})

        runner = CliRunner()
        result = runner.invoke(cli, ["generate-examples-for-word", str(words_file)])

        assert result.exit_code == 0
        assert "Preparing OpenAI API call" in result.output
        assert "Generated Examples Table:" in result.output

        output_file = tmp_path / "examples-table.md"
        assert output_file.exists()

    def test_generate_examples_with_topics(self, mocker, tmp_path):
        """Test with custom topics."""
        words_file = tmp_path / "words.md"
        words_file.write_text("kissa")
        _make_openai_mock(mocker)
        mocker.patch.dict("os.environ", {"API_KEY": "test_key"})

        runner = CliRunner()
        result = runner.invoke(
            cli, ["generate-examples-for-word", str(words_file), "--topics", "food,music,travel"]
        )

        assert result.exit_code == 0
        assert "food, music, travel" in result.output
