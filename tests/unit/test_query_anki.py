"""``query-anki list`` and the client helpers it uses, against the fake."""

import os
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from anki_helpers.anki_connect import AnkiConnect, AnkiConnectError
from anki_helpers.cli import cli
from anki_helpers.fake_anki import FakeServer, running, sample_seed

# The sample seed's day number for today.
TODAY = 20_000


@pytest.fixture
def fake() -> Iterator[FakeServer]:
    """Sample collection on a random port, used by the CLI via the env."""
    with running(sample_seed()) as server:
        os.environ["ANKI_CONNECT_URL"] = server.url
        yield server


def fronts(output: str) -> list[str]:
    """The card fronts listed in the command output, in order."""
    return [line[4:] for line in output.splitlines() if line.startswith("  • ")]


def test_today_from_review_card(fake: FakeServer) -> None:
    """The binary search recovers the collection's day number."""
    client = AnkiConnect(url=fake.url)
    (card,) = client.cards_info([2003])  # due in 5 days
    assert client.today(card["cardId"], card["due"]) == TODAY


@pytest.mark.parametrize("relative", [-36_500, -1, 0, 36_499])
def test_today_search_bounds(relative: int) -> None:
    """Every relative due in [-MAX_DUE_DAYS, MAX_DUE_DAYS) is found exactly."""
    client = AnkiConnect(url="http://unused")
    client.find_cards = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda q: [1] if relative < int(q.rsplit("<", 1)[1]) else []
    )
    assert client.today(1, 500 + relative) == 500


def test_list_sorted_by_due(fake: FakeServer) -> None:
    """Card-level flag filter, most overdue first, with relative due days."""
    result = CliRunner().invoke(cli, ["query-anki", "list", "--filter", "flag=red"])
    assert result.exit_code == 0, result.output
    assert fronts(result.output) == [
        "der Hund",
        "die Katze",
        "{{c1::Hola}}, ¿cómo {{c2::estás::verb}}?",
        "laufen",
        "schnell",
    ]
    assert "Due: -3d | Interval: 12d | Flag: red" in result.output
    assert "showing 5 of 5" in result.output


def test_list_sorted_by_interval_with_limit(fake: FakeServer) -> None:
    """--sort interval orders by interval; --limit caps the output."""
    result = CliRunner().invoke(
        cli,
        [
            "query-anki",
            "list",
            "--filter",
            "flag=red",
            "--sort",
            "interval",
            "--limit",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert fronts(result.output) == [
        "{{c1::Hola}}, ¿cómo {{c2::estás::verb}}?",
        "die Katze",
    ]
    assert "showing 2 of 5" in result.output


def test_list_due_date_filter(fake: FakeServer) -> None:
    """due_date=<2d becomes prop:due<2 and combines with the flag."""
    result = CliRunner().invoke(
        cli, ["query-anki", "list", "--filter", "flag=red:due_date=<2d"]
    )
    assert result.exit_code == 0, result.output
    assert "'flag:1 prop:due<2'" in result.output
    assert len(fronts(result.output)) == 3


def test_list_suspended_cards_go_last() -> None:
    """Cards without a due day (suspended) sort after the dated ones."""
    note = {"deck": "D", "model": "Basic", "tags": []}
    seed = {
        "notes": [
            {
                **note,
                "fields": {"Front": "paused", "Back": "x"},
                "cards": [
                    {"type": 2, "queue": -1, "due": -9, "interval": 3, "flags": 1}
                ],
            },
            {
                **note,
                "fields": {"Front": "later", "Back": "x"},
                "cards": [{"type": 2, "due": 30, "interval": 3, "flags": 1}],
            },
        ]
    }
    with running(seed) as server:
        os.environ["ANKI_CONNECT_URL"] = server.url
        result = CliRunner().invoke(cli, ["query-anki", "list", "--filter", "flag=red"])
    assert result.exit_code == 0, result.output
    assert fronts(result.output) == ["later", "paused"]
    assert "Due: - |" in result.output


def test_list_no_match(fake: FakeServer) -> None:
    """An empty result prints a notice."""
    result = CliRunner().invoke(cli, ["query-anki", "list", "--filter", "flag=purple"])
    assert result.exit_code == 0
    assert result.output == "No cards found.\n"


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("flag=bogus", "flag must be one of"),
        ("due_date=10", "due_date must look like <10d"),
        ("deck=Spanish", "unknown filter 'deck=Spanish'"),
    ],
)
def test_list_bad_filter(value: str, message: str) -> None:
    """Bad filters are usage errors (exit 2) and never reach Anki."""
    result = CliRunner().invoke(cli, ["query-anki", "list", "--filter", value])
    assert result.exit_code == 2
    assert message in result.output


def test_list_connection_error(mock_anki: MagicMock) -> None:
    """A connection error prints the error and a hint."""
    mock_anki.find_cards.side_effect = AnkiConnectError("Failed to connect")
    result = CliRunner().invoke(cli, ["query-anki", "list", "--filter", "flag=red"])
    assert "Error: Failed to connect" in result.output
    assert "Make sure Anki is running" in result.output
