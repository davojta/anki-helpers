"""End-to-end tests: installed CLI against the fake AnkiConnect server."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from anki_helpers.fake_anki import FakeServer, running, sample_seed

from .conftest import RunCli

pytestmark = pytest.mark.e2e


@pytest.fixture
def fake() -> Iterator[FakeServer]:
    """Run the fake with the bundled sample on a random port."""
    with running(sample_seed()) as server:
        yield server


def post(url: str, body: Any) -> Any:
    """POST JSON and decode the JSON reply."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def get(url: str) -> Any:
    """GET and decode the JSON reply."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def test_list_deck(fake: FakeServer, run_cli: RunCli) -> None:
    """Legacy list-deck works against the fake."""
    result = run_cli("list-deck", url=fake.url)
    assert result.returncode == 0
    assert result.stdout == (
        "Available decks:\n  • Default\n  • German\n  • German::Vocab\n  • Spanish\n"
    )


def test_list_red_flags(fake: FakeServer, run_cli: RunCli) -> None:
    """Legacy list-red-flags runs its real prop:due queries against the fake."""
    result = run_cli("list-red-flags", "--limit", "2", url=fake.url)
    assert result.returncode == 0, result.stderr
    fronts = [line for line in result.stdout.splitlines() if line.startswith("  • ")]
    assert fronts == ["  • der Hund", "  • die Katze"]
    queries = [r["params"].get("query") for r in get(f"{fake.url}/_log")]
    assert "flag:1 prop:due<0 prop:due>-7" in queries


def test_state_seed_reset(fake: FakeServer) -> None:
    """/_seed replaces the collection, /_reset restores the startup seed."""
    note = {"deck": "Only", "model": "Basic", "fields": {"Front": "x", "Back": "y"}}
    assert post(f"{fake.url}/_seed", {"notes": [note]}) == {"ok": True}
    assert post(fake.url, {"action": "deckNames", "version": 6})["result"] == [
        "Default",
        "Only",
    ]
    assert len(get(f"{fake.url}/_state")["notes"]) == 1
    post(f"{fake.url}/_reset", None)
    assert len(get(f"{fake.url}/_state")["notes"]) == 7
    assert get(f"{fake.url}/_log") == []


def test_fault_injection(fake: FakeServer, run_cli: RunCli) -> None:
    """An injected error surfaces through the legacy CLI's error path."""
    fault = {"action": "deckNames", "error": "collection is not available"}
    post(f"{fake.url}/_faults", fault)
    result = run_cli("list-deck", url=fake.url)
    assert "collection is not available" in result.stderr
    post(f"{fake.url}/_faults", [])
    assert run_cli("list-deck", url=fake.url).stdout.startswith("Available decks:")


def test_mock_serve_command(tmp_path: Path) -> None:
    """`mock serve` serves the sample and dumps state on SIGTERM."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    exe = Path(sys.prefix) / "bin" / "anki-helpers"
    dump = tmp_path / "out.json"
    proc = subprocess.Popen(
        [str(exe), "mock", "serve", "--port", str(port), "--dump-on-exit", str(dump)],
        env={k: v for k, v in os.environ.items() if k != "ANKI_CONNECT_URL"},
        stdout=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                reply = post(
                    url,
                    {"action": "createDeck", "version": 6, "params": {"deck": "New"}},
                )
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("mock serve did not start")
        assert isinstance(reply["result"], int)
    finally:
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=10)
    assert proc.returncode == 0
    assert f"listening on {url}" in out
    assert "New" in json.loads(dump.read_text())["decks"]
