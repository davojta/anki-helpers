"""End-to-end tests for full CLI execution.

These tests exercise the CLI as a black box with minimal mocks.
They use CliRunner to test the full command flow, mocking only
external HTTP endpoints (AnkiConnect, OpenAI) via responses.
"""

import os
from unittest.mock import MagicMock

import pytest
import responses
from click.testing import CliRunner

from anki_helpers.cli import cli

# Mark all tests in this module as requiring live services
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_E2E_TESTS"),
    reason="E2E tests require RUN_E2E_TESTS=1 (set to enable)",
)


class TestHelpE2E:
    """Test help system - no external mocks needed."""

    def test_main_help(self):
        """Test main help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Anki Helpers" in result.output

    def test_all_commands_have_help(self):
        """Test all commands have help text."""
        runner = CliRunner()
        commands = ["list-deck", "list-red-flags", "version", "hello-world"]
        for command in commands:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0, f"Help failed for {command}"
            assert "Usage:" in result.output


class TestListDeckE2E:
    """E2E tests for list-deck command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    @responses.activate
    def test_list_decks_full_flow(self):
        """Test full list-deck flow with mocked AnkiConnect."""
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
        assert "German" in result.output

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    @responses.activate
    def test_list_decks_empty(self):
        """Test list-deck with no decks."""
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [], "error": None},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["list-deck"])

        assert result.exit_code == 0
        assert "No decks found." in result.output


class TestListRedFlagsE2E:
    """E2E tests for list-red-flags command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    @responses.activate
    def test_list_red_flags_full_flow(self):
        """Test full list-red-flags flow with mocked AnkiConnect."""

        # Mock the chain of AnkiConnect API calls
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [101, 102], "error": None},  # findNotes
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [201, 202], "error": None},  # findCards
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [
                    {"cardId": 201, "note": 101},
                    {"cardId": 202, "note": 102},
                ],
                "error": None,
            },  # cardsInfo
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [5, 10], "error": None},  # getIntervals
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [
                    {
                        "noteId": 101,
                        "fields": {"Front": {"value": "kissa"}},
                        "tags": ["finnish"],
                    },
                    {
                        "noteId": 102,
                        "fields": {"Front": {"value": "koira"}},
                        "tags": ["finnish"],
                    },
                ],
                "error": None,
            },  # notesInfo
            status=200,
        )
        # Mock dueQuery checks (32 more calls)
        for _ in range(32):
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
        assert "koira" in result.output


class TestGetExamplesForRedFlagsCardsE2E:
    """E2E tests for get-examples-for-red-flags-cards command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    @responses.activate
    def test_full_flow_with_mocks(self, tmp_path, monkeypatch):
        """Test full flow with mocked AnkiConnect and OpenAI."""

        # Mock AnkiConnect responses for the full chain
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
            json={"result": [{"cardId": 201, "note": 101}], "error": None},
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
                "result": [
                    {
                        "noteId": 101,
                        "fields": {"Front": {"value": "testword"}},
                        "tags": [],
                    }
                ],
                "error": None,
            },
            status=200,
        )
        # 6-35: dueQuery loop
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
        ].message.content = "# Examples\n\n| Word | Example |\n|------|---------|\n| testword | This is an example. |"

        import anki_helpers.cli

        original_openai = anki_helpers.cli.OpenAI

        class MockOpenAI:
            def __init__(self, api_key):
                pass

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
            assert "Created input file" in result.output
            assert "OpenAI Response:" in result.output

            assert (tmp_path / "input-words.md").exists()
            assert (tmp_path / "results.md").exists()
            assert (tmp_path / "debug-prompt.txt").exists()

            content = (tmp_path / "input-words.md").read_text()
            assert "testword" in content

        finally:
            anki_helpers.cli.OpenAI = original_openai


class TestGenerateExamplesForWordE2E:
    """E2E tests for generate-examples-for-word command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    def test_full_flow_with_mock(self, tmp_path, monkeypatch):
        """Test full flow with mocked OpenAI."""

        words_file = tmp_path / "words.md"
        words_file.write_text("kissa\nkoira\nauto")

        # Mock OpenAI API
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = "| Word | Example |\n|------|---------|\n| kissa | Cat example |\n| koira | Dog example |\n| auto | Car example |"

        import anki_helpers.cli

        original_openai = anki_helpers.cli.OpenAI

        class MockOpenAI:
            def __init__(self, api_key):
                pass

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
            assert "Preparing OpenAI API call" in result.output
            assert "Generated Examples Table:" in result.output

            output_file = tmp_path / "examples-table.md"
            assert output_file.exists()

            content = output_file.read_text()
            assert "kissa" in content or "Cat" in content

        finally:
            anki_helpers.cli.OpenAI = original_openai

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    def test_with_custom_topics(self, tmp_path, monkeypatch):
        """Test with custom topics."""

        words_file = tmp_path / "words.md"
        words_file.write_text("kissa")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "| Word | Example |\n|------|---------|"

        import anki_helpers.cli

        original_openai = anki_helpers.cli.OpenAI

        class MockOpenAI:
            def __init__(self, api_key):
                pass

            class chat:
                class completions:
                    @staticmethod
                    def create(*args, **kwargs):
                        return mock_response

        anki_helpers.cli.OpenAI = MockOpenAI
        monkeypatch.setenv("API_KEY", "test_key")

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "generate-examples-for-word",
                    str(words_file),
                    "--topics",
                    "food,music,travel",
                ],
            )

            assert result.exit_code == 0
            assert "food, music, travel" in result.output

        finally:
            anki_helpers.cli.OpenAI = original_openai


class TestVersionE2E:
    """E2E tests for version command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    def test_version_e2e(self):
        """Test version command end-to-end."""
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "Anki Helpers version" in result.output


class TestHelloWorldE2E:
    """E2E tests for hello-world command."""

    @pytest.mark.skipif(not os.environ.get("RUN_E2E_TESTS"), reason="Needs RUN_E2E_TESTS=1")
    def test_hello_world_e2e(self):
        """Test hello-world command end-to-end."""
        runner = CliRunner()
        result = runner.invoke(cli, ["hello-world"])
        assert result.exit_code == 0
        assert "Hello World!" in result.output
