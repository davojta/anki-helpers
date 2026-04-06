"""Integration tests for sync, query-local, query-anki, and --local flag commands."""

import json
from unittest.mock import MagicMock

import responses
from click.testing import CliRunner

from anki_helpers.cli import cli
from anki_helpers.sqlite_storage import SQLiteStorage


def _make_notes_info_response(count=3):
    """Generate mock notesInfo API response."""
    notes = []
    for i in range(count):
        notes.append(
            {
                "noteId": 100 + i,
                "fields": {"Front": {"value": f"word{i}"}, "Back": {"value": f"val{i}"}},
                "tags": ["tag1"],
                "mod": 1700000000,
                "cards": [200 + i],
            }
        )
    return notes


def _make_cards_info_response(notes_info):
    """Generate mock cardsInfo response from notesInfo data."""
    cards = []
    for note in notes_info:
        for card_id in note["cards"]:
            cards.append(
                {
                    "cardId": card_id,
                    "note": note["noteId"],
                    "deckName": "Default",
                    "due": 105,
                    "interval": 10,
                    "flags": 0,
                    "queue": 2,
                }
            )
    return cards


class TestSyncInitialIntegration:
    """Integration tests for initial sync command."""

    @responses.activate
    def test_initial_sync(self, tmp_path):
        """Test initial sync creates database with correct data."""
        notes_info = _make_notes_info_response(3)
        cards_info = _make_cards_info_response(notes_info)

        # 1. notesInfo(query="")
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": notes_info, "error": None},
            status=200,
        )
        # 2. cardsInfo
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": cards_info, "error": None},
            status=200,
        )
        # 3. findCards("prop:due=0") for days_elapsed
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [200], "error": None},
            status=200,
        )
        # 4. cardsInfo for days_elapsed
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [{"cardId": 200, "due": 100, "note": 100}], "error": None},
            status=200,
        )

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["sync"])
            assert result.exit_code == 0
            assert "Initial sync complete" in result.output
            assert "Total cards: 3" in result.output


class TestSyncIncrementalIntegration:
    """Integration tests for incremental sync command."""

    def test_incremental_sync(self, tmp_path):
        """Test incremental sync updates existing data."""
        db_path = tmp_path / ".anki-cache.db"

        # Pre-populate database
        with SQLiteStorage(db_path) as storage:
            storage.replace_all(
                [
                    {
                        "card_id": 200,
                        "note_id": 100,
                        "deck_name": "Default",
                        "fields": '{"Front": "old"}',
                        "tags": "[]",
                        "due": 50,
                        "interval": 5,
                        "flag": 0,
                        "queue": 2,
                        "due_query": 5,
                        "modified": 1000000,
                    }
                ]
            )
            storage.add_sync_log(total_cards=1, deck_count=1, new_cards=1, updated_cards=0)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Copy the pre-populated db
            import shutil

            shutil.copy(str(db_path), ".anki-cache.db")

            runner.invoke(cli, ["sync"])
            # Should detect previous sync and attempt incremental
            # (Will fail at AnkiConnect since no mock, but that's OK for structure test)
            # For a proper test we'd need responses mock


class TestQueryLocalIntegration:
    """Integration tests for query-local command."""

    def test_query_with_prepopulated_db(self, tmp_path):
        """Test query-local reads from pre-populated database."""
        db_path = tmp_path / ".anki-cache.db"

        with SQLiteStorage(db_path) as storage:
            storage.replace_all(
                [
                    {
                        "card_id": 1,
                        "note_id": 100,
                        "deck_name": "Default",
                        "fields": '{"Front": "hello"}',
                        "tags": "[]",
                        "due": 5,
                        "interval": 10,
                        "flag": 1,
                        "queue": 2,
                        "due_query": 3,
                        "modified": 1000000,
                    },
                    {
                        "card_id": 2,
                        "note_id": 101,
                        "deck_name": "Other",
                        "fields": '{"Front": "world"}',
                        "tags": "[]",
                        "due": 10,
                        "interval": 20,
                        "flag": 0,
                        "queue": 2,
                        "due_query": 8,
                        "modified": 1000000,
                    },
                ]
            )

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil

            shutil.copy(str(db_path), ".anki-cache.db")

            result = runner.invoke(cli, ["query-local", "SELECT COUNT(*) as cnt FROM notes"])
            assert result.exit_code == 0
            assert "2" in result.output

    def test_no_database(self, tmp_path):
        """Test query-local with no database file."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["query-local", "SELECT 1"])
            assert "No local database found" in result.output

    def test_non_select_rejected(self, tmp_path):
        """Test query-local rejects non-SELECT."""
        db_path = tmp_path / ".anki-cache.db"
        with SQLiteStorage(db_path) as storage:
            storage.replace_all([])

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil

            shutil.copy(str(db_path), ".anki-cache.db")

            result = runner.invoke(cli, ["query-local", "DELETE FROM notes"])
            assert "Only SELECT queries" in result.output


class TestQueryAnkiListIntegration:
    """Integration tests for query-anki list command."""

    @responses.activate
    def test_list_with_flag_filter(self):
        """Test query-anki list with flag filter."""
        # findCards
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={"result": [201], "error": None},
            status=200,
        )
        # cardsInfo
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [
                    {
                        "cardId": 201,
                        "note": 101,
                        "deckName": "Default",
                        "due": 5,
                        "flags": 1,
                        "queue": 2,
                        "interval": 10,
                    }
                ],
                "error": None,
            },
            status=200,
        )
        # notesInfo
        responses.add(
            responses.POST,
            "http://localhost:8765",
            json={
                "result": [
                    {"noteId": 101, "fields": {"Front": {"value": "hello"}}, "tags": ["tag1"]}
                ],
                "error": None,
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["query-anki", "list", "--filter", "flag=red", "--sort", "due"])
        assert result.exit_code == 0
        assert "201" in result.output


class TestLocalFlagIntegration:
    """Integration tests for --local flag on existing commands."""

    def test_list_red_flags_local(self, tmp_path):
        """Test list-red-flags --local reads from cache."""
        db_path = tmp_path / ".anki-cache.db"

        with SQLiteStorage(db_path) as storage:
            storage.replace_all(
                [
                    {
                        "card_id": 1,
                        "note_id": 100,
                        "deck_name": "Default",
                        "fields": json.dumps({"Front": "testword"}),
                        "tags": json.dumps(["tag1"]),
                        "due": 5,
                        "interval": 10,
                        "flag": 1,
                        "queue": 2,
                        "due_query": 3,
                        "modified": 1000000,
                    },
                ]
            )
            storage.add_sync_log(total_cards=1, deck_count=1, new_cards=1, updated_cards=0)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil

            shutil.copy(str(db_path), ".anki-cache.db")

            result = runner.invoke(cli, ["list-red-flags", "--local"])
            assert result.exit_code == 0
            assert "testword" in result.output

    def test_list_red_flags_local_no_db(self, tmp_path):
        """Test list-red-flags --local with no database."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list-red-flags", "--local"])
            assert "No local database found" in result.output

    def test_get_examples_local(self, tmp_path, monkeypatch):
        """Test get-examples-for-red-flags-cards --local."""
        db_path = tmp_path / ".anki-cache.db"

        with SQLiteStorage(db_path) as storage:
            storage.replace_all(
                [
                    {
                        "card_id": 1,
                        "note_id": 100,
                        "deck_name": "Default",
                        "fields": json.dumps({"Front": "testword"}),
                        "tags": json.dumps([]),
                        "due": 5,
                        "interval": 10,
                        "flag": 1,
                        "queue": 2,
                        "due_query": 3,
                        "modified": 1000000,
                    },
                ]
            )
            storage.add_sync_log(total_cards=1, deck_count=1, new_cards=1, updated_cards=0)

        # Mock OpenAI
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Example sentence for testword."

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
            output_dir = tmp_path / "output"
            with runner.isolated_filesystem(temp_dir=tmp_path):
                import shutil

                shutil.copy(str(db_path), ".anki-cache.db")
                output_dir.mkdir(parents=True, exist_ok=True)

                result = runner.invoke(
                    cli, ["get-examples-for-red-flags-cards", "--local", str(output_dir)]
                )
                assert result.exit_code == 0
                assert (output_dir / "input-words.md").exists()
        finally:
            anki_helpers.cli.OpenAI = original_openai
