"""HTTP front end for ``FakeAnki``, compatible with AnkiConnect clients.

``POST /`` takes an AnkiConnect request body. Debug endpoints:

- ``GET /_state`` — dump the collection as a seed document
- ``GET /_log`` — request bodies received so far
- ``POST /_reset`` — reload the startup seed, clear log and faults
- ``POST /_seed`` — replace the collection with the posted seed document
- ``POST /_faults`` — ``{"action", "error"?, "latency_ms"?, "times"?}``; ``[]`` clears
"""

import json
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from .actions import FakeAnki, Fault
from .state import Clock, dump_state, load_state, system_clock


@dataclass
class FakeServer:
    """A running fake: the ``FakeAnki`` plus its HTTP server."""

    anki: FakeAnki
    seed: dict[str, Any] = field(default_factory=dict[str, Any])
    clock: Clock = system_clock
    httpd: ThreadingHTTPServer = field(init=False)

    @property
    def url(self) -> str:
        """Base URL, e.g. ``http://127.0.0.1:8765``."""
        host, port = self.httpd.server_address[:2]
        return f"http://{host!s}:{port}"

    def reset(self, seed: dict[str, Any] | None = None) -> None:
        """Replace state with ``seed`` (default: startup seed); clear log/faults."""
        state = load_state(self.seed if seed is None else seed, self.clock)
        with self.anki.lock:
            self.anki.state = state
            self.anki.log.clear()
            self.anki.faults.clear()


def _handler(server: FakeServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> Any:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            return json.loads(raw) if raw.strip() else None

        def do_OPTIONS(self) -> None:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            match self.path:
                case "/_state":
                    with server.anki.lock:
                        self._send(dump_state(server.anki.state))
                case "/_log":
                    with server.anki.lock:
                        self._send(list(server.anki.log))
                case _:
                    self._send("AnkiConnect v.6 (fake)")

        def do_POST(self) -> None:
            try:
                body = self._body()
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self._send({"result": None, "error": f"invalid JSON: {e}"}, 400)
                return
            match self.path:
                case "/_reset":
                    server.reset()
                    self._send({"ok": True})
                case "/_seed":
                    try:
                        if not isinstance(body, dict | None):
                            raise TypeError("seed must be an object")
                        server.reset(cast("dict[str, Any]", body or {}))
                    except (AttributeError, KeyError, TypeError, ValueError) as e:
                        self._send({"ok": False, "error": f"bad seed: {e!r}"}, 400)
                        return
                    self._send({"ok": True})
                case "/_faults":
                    items = cast(
                        "list[Any]", body if isinstance(body, list) else [body]
                    )
                    try:
                        faults = [Fault(**item) for item in items]
                    except TypeError as e:
                        self._send({"ok": False, "error": f"bad fault: {e}"}, 400)
                        return
                    with server.anki.lock:
                        if not faults:
                            server.anki.faults.clear()
                        server.anki.faults.extend(faults)
                    self._send({"ok": True})
                case _:
                    if not isinstance(body, dict):
                        self._send(
                            {"result": None, "error": "request must be an object"}
                        )
                        return
                    self._send(server.anki.handle(cast("dict[str, Any]", body)))

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


def make_server(
    seed: dict[str, Any] | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    clock: Clock = system_clock,
) -> FakeServer:
    """Build (not start) a fake server; ``port=0`` picks a free port."""
    seed = seed or {}
    anki = FakeAnki(state=load_state(seed, clock))
    server = FakeServer(anki=anki, seed=seed, clock=clock)
    server.httpd = ThreadingHTTPServer((host, port), _handler(server))
    server.httpd.daemon_threads = True
    return server


@contextmanager
def running(
    seed: dict[str, Any] | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    clock: Clock = system_clock,
) -> Generator[FakeServer]:
    """Run a fake server in a background thread for the duration of the block."""
    server = make_server(seed, host, port, clock)
    thread = threading.Thread(target=server.httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.httpd.shutdown()
        server.httpd.server_close()
        thread.join(timeout=5)
