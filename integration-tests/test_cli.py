"""Integration tests for CLI commands.

These tests invoke CLI commands via CliRunner with mocked HTTP responses
to test the full command execution path including HTTP layer.
"""

from unittest.mock import MagicMock

import responses
from click.testing import CliRunner

from anki_helpers.cli import cli


class TestVersionCommand:
    """Test the version command."""

    def test_version(self):
        """Test version command output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "Anki Helpers version" in result.output


class TestHelpCommand:
    """Test help functionality."""

    def test_main_help(self):
        """Test main help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_all_commands_have_help(self):
        """Test all commands have help text."""
        runner = CliRunner()
        for command in ["list-deck", "list-red-flags", "version", "hello-world"]:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.output


class TestListDeckIntegration:
    """Integration tests for list-deck command."""

    @responses.activate
    def test_list_decks_with_http_mock(self):
        """Test list-deck with mocked HTTP responses."""

        # Mock the AnkiConnect HTTP response
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": ["Default", "Finnish", "German"], "error": None},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "Available decks:" in result.output
        assert "Default" in result.output
        assert "Finnish" in result.output

    @responses.activate
    def test_list_decks_http_error(self):
        """Test list-deck handles HTTP errors."""

        # Mock an API error response from AnkiConnect
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": None, "error": "Invalid action"},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "Error:" in result.output
        assert "AnkiConnect error" in result.output


class TestListRedFlagsIntegration:
    """Integration tests for list-red-flags command."""

    @responses.activate
    def test_list_red_flags_with_http_mock(self, monkeypatch):
        """Test list-red-flags with mocked HTTP responses."""

        # Chain of API calls made by find_cards_with_red_flag_sorted
        # 1. findNotes flag:1
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [101], "error": None},
            status=200,
        )
        # 2. findCards nid:101
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [201], "error": None},
            status=200,
        )
        # 3. cardsInfo
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [{"cardId": 201, "note": 101}],
                "error": None,
            },
            status=200,
        )
        # 4. getIntervals
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [5], "error": None},
            status=200,
        )
        # 5. notesInfo
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [{"noteId": 101, "fields": {"Front": {"value": "kissa"}}, "tags": []}],
                "error": None,
            },
            status=200,
        )
        # 6-35: Multiple findNotes calls for dueQuery (30 iterations)
        for _i in range(30):
            responses.add(
                responses.POST,
                "http://localhost:8765",
                json={"result": [], "error": None},
                status=200,
            )

        runner = CliRunner()
        result = runner.invoke(cli, ["list-red-flags"])

        assert result.exit_code == 0
        assert "Cards with red flags" in result.output
        assert "kissa" in result.output


class TestGetExamplesForRedFlagsCardsIntegration:
    """Integration tests for get-examples-for-red-flags-cards."""

    @responses.activate
    def test_full_flow_with_mocks(self, tmp_path, monkeypatch):
        """Test full flow with mocked AnkiConnect and OpenAI."""

        # Mock AnkiConnect responses
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [101], "error": None},
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [201], "error": None},
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [{"cardId": 201, "note": 101}], "error": None},
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [5], "error": None},
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [{"noteId": 101, "fields": {"Front": {"value": "testword"}}, "tags": []}],
                "error": None,
            },
            status=200,
        )
        # 30 more for dueQuery loop
        for _ in range(30):
            responses.add(
                responses.POST,
                "http://localhost:8765",
                json={"result": [], "error": None},
                status=200,
            )

        # Mock OpenAI API
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = (
            "| Word | Example |\n|------|---------|\n| testword | Example sentence. |"
        )

        import anki_helpers.cli

        original_openai = anki_helpers.cli.OpenAI

        class MockOpenAI:
            def __init__(self, api_key):
                self.api_key = api_key

            class chat:
                class completions:
                    @staticmethod
                    def create(*args, **kwargs):
                        return mock_response

        anki_helpers.cli.OpenAI = MockOpenAI
        monkeypatch.setenv("API_KEY", "test_key")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["get-examples-for-red-flags-cards", str(tmp_path)])

            assert result.exit_code == 0
            assert (tmp_path / "input-words.md").exists()
            assert (tmp_path / "results.md").exists()
        finally:
            anki_helpers.cli.OpenAI = original_openai


class TestGenerateExamplesForWordIntegration:
    """Integration tests for generate-examples-for-word."""

    def test_full_flow_with_mock(self, tmp_path, monkeypatch):
        """Test full flow with mocked OpenAI."""

        words_file = tmp_path / "words.md"
        words_file.write_text("kissa\nkoira")

        # Mock OpenAI API
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "| Word | Example |\n|------|---------|"

        import anki_helpers.cli

        original_openai = anki_helpers.cli.OpenAI

        class MockOpenAI:
            def __init__(self, api_key):
                self.api_key = api_key

            class chat:
                class completions:
                    @staticmethod
                    def create(*args, **kwargs):
                        return mock_response

        anki_helpers.cli.OpenAI = MockOpenAI
        monkeypatch.setenv("API_KEY", "test_key")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["generate-examples-for-word", str(words_file)])

            assert result.exit_code == 0
            assert (tmp_path / "examples-table.md").exists()
        finally:
            anki_helpers.cli.OpenAI = original_openai
