"""Unit tests for sync mode detection logic and new AnkiConnect methods."""

from unittest.mock import MagicMock

import pytest

from anki_helpers.anki_connect import AnkiConnect
from anki_helpers.sqlite_storage import SQLiteStorage


class TestSyncModeDetection:
    def test_first_sync_is_initial(self, tmp_path):
        """No previous sync_log → initial sync path."""
        with SQLiteStorage(tmp_path / "test.db") as storage:
            assert storage.get_last_sync() is None

    def test_subsequent_sync_is_incremental(self, tmp_path):
        """Previous sync_log exists → incremental sync path."""
        with SQLiteStorage(tmp_path / "test.db") as storage:
            storage.add_sync_log(total_cards=10, deck_count=1, new_cards=10, updated_cards=0)
            assert storage.get_last_sync() is not None


class TestAnkiConnectNewMethods:
    def test_get_all_notes_info(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.get_all_notes_info.return_value = [{"noteId": 1}]
        result = anki.get_all_notes_info()
        assert len(result) == 1

    def test_get_cards_info(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.get_cards_info.return_value = [{"cardId": 1}]
        result = anki.get_cards_info([1])
        assert len(result) == 1

    def test_get_cards_info_empty(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.get_cards_info.return_value = []
        result = anki.get_cards_info([])
        assert result == []

    def test_find_edited_notes(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.find_edited_notes.return_value = [1, 2]
        result = anki.find_edited_notes(7)
        assert result == [1, 2]

    def test_find_notes_info(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.find_notes_info.return_value = [{"noteId": 1}]
        result = anki.find_notes_info([1])
        assert len(result) == 1

    def test_find_notes_info_empty(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.find_notes_info.return_value = []
        result = anki.find_notes_info([])
        assert result == []

    def test_find_cards(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.find_cards.return_value = [1, 2]
        result = anki.find_cards("flag:1")
        assert result == [1, 2]

    def test_get_days_elapsed(self):
        anki = MagicMock(spec=AnkiConnect)
        anki.get_days_elapsed.return_value = 100
        result = anki.get_days_elapsed()
        assert result == 100


class TestFilterParser:
    def test_single_filter(self):
        from anki_helpers.cli import parse_filters

        result = parse_filters("flag=red")
        assert result == [("flag", "red")]

    def test_multiple_filters(self):
        from anki_helpers.cli import parse_filters

        result = parse_filters("flag=red:due_date=<10d")
        assert result == [("flag", "red"), ("due_date", "<10d")]

    def test_unknown_key(self):
        import click

        from anki_helpers.cli import parse_filters

        with pytest.raises(click.BadParameter, match="Unknown filter"):
            parse_filters("unknown=value")

    def test_invalid_flag_value(self):
        import click

        from anki_helpers.cli import parse_filters

        with pytest.raises(click.BadParameter, match="Invalid flag value"):
            parse_filters("flag=yellow")

    def test_invalid_due_date_format(self):
        import click

        from anki_helpers.cli import parse_filters

        with pytest.raises(click.BadParameter, match="Invalid due_date format"):
            parse_filters("due_date=10")


class TestFiltersToAnkiQuery:
    def test_flag_red(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "red")]) == "flag:1"

    def test_flag_none(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "none")]) == "flag:0"

    def test_flag_orange(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "orange")]) == "flag:2"

    def test_flag_green(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "green")]) == "flag:3"

    def test_flag_blue(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "blue")]) == "flag:4"

    def test_flag_pink(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "pink")]) == "flag:5"

    def test_flag_turquoise(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "turquoise")]) == "flag:6"

    def test_flag_purple(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("flag", "purple")]) == "flag:7"

    def test_due_date_less_than(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("due_date", "<10d")]) == "prop:due<10"

    def test_due_date_greater_than(self):
        from anki_helpers.cli import filters_to_anki_query

        assert filters_to_anki_query([("due_date", ">5d")]) == "prop:due>5"

    def test_combined(self):
        from anki_helpers.cli import filters_to_anki_query

        result = filters_to_anki_query([("flag", "red"), ("due_date", "<10d")])
        assert result == "flag:1 prop:due<10"
