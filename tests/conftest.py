"""Pytest configuration and fixtures for unit tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_anki_connect():
    """Create a mock AnkiConnect client for testing."""
    return MagicMock()


@pytest.fixture
def mock_openai():
    """Create a mock OpenAI client for testing."""
    return MagicMock()
