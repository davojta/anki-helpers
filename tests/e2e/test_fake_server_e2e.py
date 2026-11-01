"""End-to-end tests: installed CLI against the fake AnkiConnect server."""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def test_list_red_flags_default_limit_and_order(
    fake: FakeServer, run_cli: RunCli
) -> None:
    """Default --limit is 5; order is by dueQuery ascending (overdue first).

    Pins today's behaviour; S1-07 asks for "due desc" (see PR notes).
    """
    result = run_cli("list-red-flags", url=fake.url)
    assert result.returncode == 0, result.stderr
    fronts = [line for line in result.stdout.splitlines() if line.startswith("  • ")]
    assert fronts == [
        "  • der Hund",
        "  • die Katze",
        "  • {{c1::Hola}}, ¿cómo {{c2::estás::verb}}?",
        "  • {{c1::Hola}}, ¿cómo {{c2::estás::verb}}?",
        "  • laufen",
    ]
    assert "showing top 5" in result.stdout


@pytest.fixture
def openai_stub() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Answer OpenAI chat completions with a fixed reply; record request bodies."""
    bodies: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            bodies.append(json.loads(self.rfile.read(length)))
            data = json.dumps(
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "gpt-4o",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "STUB REPLY"},
                            "finish_reason": "stop",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1", bodies
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_get_examples_for_red_flags_cards(
    fake: FakeServer,
    run_cli: RunCli,
    openai_stub: tuple[str, list[dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """Red-flag words from the fake go into the prompt; the reply is saved."""
    base_url, bodies = openai_stub
    out = tmp_path / "out"
    result = run_cli(
        "get-examples-for-red-flags-cards",
        "--limit",
        "3",
        str(out),
        url=fake.url,
        env={"API_KEY": "test-key", "OPENAI_BASE_URL": base_url},
    )
    assert result.returncode == 0, result.stderr
    assert "Error" not in result.stderr
    assert (out / "input-words.md").read_text() == "der Hund\ndie Katze\nlaufen"
    assert (out / "results.md").read_text() == "STUB REPLY"
    assert len(bodies) == 1
    assert "der Hund" in bodies[0]["messages"][1]["content"]


def test_generate_examples_for_word(
    run_cli: RunCli,
    openai_stub: tuple[str, list[dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """The installed CLI sends the words with the default topics; reply saved."""
    base_url, bodies = openai_stub
    words = tmp_path / "words.md"
    words.write_text("talo\n")
    result = run_cli(
        "generate-examples-for-word",
        str(words),
        url="http://unused",
        env={"API_KEY": "test-key", "OPENAI_BASE_URL": base_url},
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "examples-table.md").read_text() == "STUB REPLY"
    prompt = bodies[0]["messages"][1]["content"]
    assert "theme of cycling as a hobby in finland" in prompt
    assert prompt.endswith("talo\n")


def test_query_anki_list(fake: FakeServer, run_cli: RunCli) -> None:
    """The installed query-anki list command sorts the fake's red cards by due."""
    result = run_cli("query-anki", "list", "--filter", "flag=red", url=fake.url)
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith("  • ")]
    assert lines[:2] == ["  • der Hund", "  • die Katze"]


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


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/_faults", None),
        ("/_faults", {}),
        ("/_faults", {"bogus": 1}),
        ("/_seed", [1, 2]),
    ],
)
def test_bad_debug_bodies_get_400(fake: FakeServer, path: str, body: Any) -> None:
    """Malformed debug requests get a 400 instead of a dropped connection."""
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        post(f"{fake.url}{path}", body)
    assert exc_info.value.code == 400
    assert post(fake.url, {"action": "version", "version": 6})["result"] == 6
