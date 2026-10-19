"""Unit tests for the ``mock`` CLI group."""

import json
from pathlib import Path

from click.testing import CliRunner

from anki_helpers.cli import cli


def test_query_notes() -> None:
    """Mock query prints matching notes of the bundled sample."""
    result = CliRunner().invoke(cli, ["mock", "query", "flag:1 prop:due<=0"])
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "2 note(s) match 'flag:1 prop:due<=0'",
        "  1001  der Hund  [noun, animals]",
        "  1002  die Katze  [noun, animals]",
    ]


def test_query_cards() -> None:
    """--cards matches cards and shows deck and template ord."""
    result = CliRunner().invoke(cli, ["mock", "query", "--cards", "nid:1004"])
    assert result.exit_code == 0
    assert "  2005  schnell  [German::Vocab ord=1]" in result.output


def test_query_with_seed_file(tmp_path: Path) -> None:
    """--seed loads a custom collection; --empty starts blank."""
    seed = tmp_path / "seed.json"
    note = {"deck": "D", "model": "Basic", "fields": {"Front": "hi", "Back": ""}}
    seed.write_text(json.dumps({"notes": [note]}))
    result = CliRunner().invoke(cli, ["mock", "query", "--seed", str(seed), "deck:D"])
    assert "1 note(s) match" in result.output
    result = CliRunner().invoke(cli, ["mock", "query", "--empty", ""])
    assert "0 note(s) match" in result.output


def test_query_unsupported() -> None:
    """Unsupported syntax exits non-zero with the reason."""
    result = CliRunner().invoke(cli, ["mock", "query", "added:1"])
    assert result.exit_code == 1
    assert "unsupported search: added:1" in result.output
