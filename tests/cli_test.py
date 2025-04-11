"""Tests for the CLI module."""

from click.testing import CliRunner

from anki_helpers.cli import cli


def test_version():
    """Test the version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "Anki Helpers version" in result.output
