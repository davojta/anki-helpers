"""End-to-end tests for full CLI execution.

These tests exercise the CLI as a black box in isolated environments.
They require AnkiConnect to be running and a valid OpenAI API key.
"""

import os
import subprocess

import pytest

# Mark all tests in this module as requiring live services
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_E2E_TESTS"),
    reason="E2E tests require RUN_E2E_TESTS=1 and live services",
)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run the CLI from the installed entry point."""
    cmd = ["anki-helpers"] + args
    env = os.environ.copy()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, result.stdout, result.stderr


class TestCLIE2E:
    """Test full CLI workflows."""

    def test_version_e2e(self):
        """Test version command end-to-end."""
        exit_code, stdout, stderr = run_cli(["version"])
        assert exit_code == 0
        assert "Anki Helpers version" in stdout

    def test_help_system_e2e(self):
        """Test the complete help system."""
        exit_code, stdout, stderr = run_cli(["--help"])
        assert exit_code == 0
        assert "Usage:" in stdout

        for command in ["list-deck", "list-red-flags", "version"]:
            exit_code, stdout, stderr = run_cli([command, "--help"])
            assert exit_code == 0
            assert "Usage:" in stdout
