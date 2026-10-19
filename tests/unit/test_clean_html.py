"""Unit tests for clean_html_content."""

import pytest

from anki_helpers.cli import clean_html_content


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain", "plain"),
        ("<b>bold</b> text", "bold text"),
        ("a&nbsp;b", "a b"),
        ("fish &amp; chips", "fish & chips"),
        ("word [sound:file.mp3]", "word"),
        ("  many \n  spaces\t here ", "many spaces here"),
        ("<div>one</div><div>two</div>", "onetwo"),
        ("", ""),
    ],
)
def test_clean_html_content(raw: str, expected: str) -> None:
    """HTML tags, entities, sound tags and extra whitespace are cleaned."""
    assert clean_html_content(raw) == expected
