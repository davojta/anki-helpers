"""Integration tests for CLI commands.

These tests invoke CLI commands via subprocess to test the full
command execution path, but mock external services (AnkiConnect, OpenAI).
"""

import subprocess
import sys


def run_cli_command(args: list[str]) -> tuple[int, str, str]:
    """Run the CLI command and return exit code, stdout, and stderr."""
    cmd = [sys.executable, "-m", "anki_helpers.cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


class TestVersionCommand:
    """Test the version command."""

    def test_version(self):
        """Test version command output."""
        exit_code, stdout, stderr = run_cli_command(["version"])
        assert exit_code == 0
        assert "Anki Helpers version" in stdout
        assert stderr == ""


class TestHelpCommand:
    """Test help functionality."""

    def test_main_help(self):
        """Test main help command."""
        exit_code, stdout, stderr = run_cli_command(["--help"])
        assert exit_code == 0
        assert "Usage:" in stdout
        assert stderr == ""
