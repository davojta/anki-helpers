"""Tests for the CLI module."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

# Add the src directory to the Python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from anki_helpers.cli import cli  # noqa: E402


# Mock OpenAI class
class OpenAI:
    """Mock implementation of the OpenAI client for testing."""

    def __init__(self, api_key=None):
        """Initialize mock OpenAI client with API key.

        Args:
            api_key: Optional API key for authentication
        """
        self.api_key = api_key
        self.chat = ChatCompletions(api_key)


class ChatCompletions:
    """Mock implementation of the ChatCompletions API."""

    def __init__(self, api_key=None):
        """Initialize mock ChatCompletions with API key.

        Args:
            api_key: Optional API key for authentication
        """
        self.api_key = api_key
        self.completions = self

    def create(self, model=None, messages=None):
        """Mock the create method that generates completions.

        Args:
            model: Model name to use for generation
            messages: List of message objects

        Returns:
            MockResponse object with test content
        """
        print(f"Would call OpenAI API with model {model} and {len(messages)} messages")
        return MockResponse(
            "This is a mock response from OpenAI API. Please install the openai package to get actual responses."
        )


class MockResponse:
    """Mock response object returned by the OpenAI API."""

    def __init__(self, content):
        """Initialize mock response with content.

        Args:
            content: Text content for the response
        """
        self.choices = [MockChoice(content)]


class MockChoice:
    """Mock choice object contained in API responses."""

    def __init__(self, content):
        """Initialize mock choice with content.

        Args:
            content: Text content for the message
        """
        self.message = MockMessage(content)


class MockMessage:
    """Mock message object within a choice."""

    def __init__(self, content):
        """Initialize mock message with content.

        Args:
            content: Text content of the message
        """
        self.content = content


def test_version():
    """Test the version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "Anki Helpers version" in result.output


@patch("anki_helpers.cli.AnkiConnect")
@patch("anki_helpers.cli.OpenAI", OpenAI)
@patch.dict("os.environ", {"API_KEY": "test_api_key"})
def test_get_examples_for_red_flags_cards(mock_anki_connect):
    """Test the get_examples_for_red_flags_cards command.

    This test verifies that the command correctly:
    1. Retrieves red-flagged cards from Anki
    2. Creates input-words.md file with card content
    3. Calls OpenAI API to generate examples
    4. Writes results to results.md file

    Args:
        mock_anki_connect: Mocked AnkiConnect class
    """
    """Test the get_examples_for_red_flags_cards command."""
    # Setup mock AnkiConnect
    mock_anki = MagicMock()
    mock_anki_connect.return_value = mock_anki

    # Mock the find_cards_with_red_flag_sorted method to return some test cards
    mock_anki.find_cards_with_red_flag_sorted.return_value = [
        {
            "noteFields": {
                "Front": {"value": "test word 1"},
            }
        },
        {
            "noteFields": {
                "Front": {"value": "test word 2"},
            }
        },
        {
            "noteFields": {
                "Front": {"value": "test word 3"},
            }
        },
    ]

    # Test case 1: Without limit (default behavior)
    with tempfile.TemporaryDirectory() as temp_dir:
        runner = CliRunner()
        result = runner.invoke(cli, ["get-examples-for-red-flags-cards", temp_dir])

        # Check that the command executed successfully
        assert result.exit_code == 0

        # Check that the input file was created
        input_file_path = Path(temp_dir) / "input-words.md"
        assert input_file_path.exists()

        # Check that the results file was created
        results_file_path = Path(temp_dir) / "results.md"
        assert results_file_path.exists()

        # Check the content of the input file
        with open(input_file_path, "r") as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" in content

    # Test case 2: With limit parameter
    with tempfile.TemporaryDirectory() as temp_dir:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["get-examples-for-red-flags-cards", "--limit", "2", temp_dir]
        )

        # Check that the command executed successfully
        assert result.exit_code == 0

        # Check that the input file was created
        input_file_path = Path(temp_dir) / "input-words.md"
        assert input_file_path.exists()

        # Check the content of the input file
        with open(input_file_path, "r") as f:
            content = f.read()
            assert "test word 1" in content
            assert "test word 2" in content
            assert "test word 3" not in content

    # Check that the mock was called
    assert mock_anki.find_cards_with_red_flag_sorted.call_count == 2
