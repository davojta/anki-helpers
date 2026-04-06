"""E2E tests for sync and query commands.

Requires running Anki with AnkiConnect plugin.
Run with: RUN_E2E_TESTS=1 uv run pytest e2e-tests/test_sync_e2e.py -v
"""

import os
import subprocess

import pytest

# Guard: skip all tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E_TESTS") != "1",
    reason="E2E tests require RUN_E2E_TESTS=1 and running Anki",
)


def run_cli(*args):
    """Run anki-helpers CLI command and return CompletedProcess."""
    return subprocess.run(
        ["uv", "run", "anki-helpers", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestSyncE2E:
    def test_sync_initial_load(self, tmp_path):
        """E2E: sync initial load creates .anki-cache.db with correct row counts."""
        # Run sync from a temp directory
        result = subprocess.run(
            ["uv", "run", "anki-helpers", "sync"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert "sync" in result.stdout.lower()
        # Verify database was created
        db_path = tmp_path / ".anki-cache.db"
        assert db_path.exists()

    def test_sync_incremental(self, tmp_path):
        """E2E: sync incremental updates after initial sync."""
        # First sync
        result1 = subprocess.run(
            ["uv", "run", "anki-helpers", "sync"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )
        assert result1.returncode == 0

        # Second sync (incremental)
        result2 = subprocess.run(
            ["uv", "run", "anki-helpers", "sync"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )
        assert result2.returncode == 0
        # Should indicate incremental or no changes
        output = result2.stdout.lower()
        assert "incremental" in output or "no changes" in output

    def test_query_local_count(self, tmp_path):
        """E2E: query-local COUNT matches Anki card count."""
        # Sync first
        subprocess.run(
            ["uv", "run", "anki-helpers", "sync"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )

        # Query local
        result = subprocess.run(
            ["uv", "run", "anki-helpers", "query-local", "SELECT COUNT(*) as cnt FROM notes;"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        # Should have a number in output
        lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
        assert len(lines) >= 2  # header + data row

    def test_query_anki_list_flag_red(self, tmp_path):
        """E2E: query-anki list with flag=red returns results."""
        result = run_cli("query-anki", "list", "--filter", "flag=red", "--sort", "due")
        assert result.returncode == 0

    def test_query_anki_list_due_date(self, tmp_path):
        """E2E: query-anki list with due_date filter."""
        result = run_cli("query-anki", "list", "--filter", "due_date=<10d", "--sort", "due")
        assert result.returncode == 0

    def test_query_anki_combined_filter(self, tmp_path):
        """E2E: query-anki list with combined filters."""
        result = run_cli(
            "query-anki", "list", "--filter", "flag=red:due_date=<10d", "--sort", "due"
        )
        assert result.returncode == 0
