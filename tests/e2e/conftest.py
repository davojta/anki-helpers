"""Fixtures for e2e tests: a stub AnkiConnect HTTP server and a CLI runner."""

import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

RunCli = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass
class AnkiStub:
    """Handle on the running stub server."""

    url: str
    responses: dict[str, Any] = field(default_factory=dict)
    requests: list[dict[str, Any]] = field(default_factory=list)


def _make_handler(stub: AnkiStub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            stub.requests.append(body)
            result = stub.responses.get(body["action"])
            if callable(result):
                result = result(body.get("params", {}))
            data = json.dumps({"result": result, "error": None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@pytest.fixture
def anki_stub() -> Iterator[AnkiStub]:
    """Run a stub AnkiConnect server on 127.0.0.1 for the duration of a test."""
    stub = AnkiStub(url="")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(stub))
    stub.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield stub
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def run_cli(tmp_path: Path) -> RunCli:
    """Return a helper that runs the installed anki-helpers executable."""
    exe = Path(sys.prefix) / "bin" / "anki-helpers"
    executable = str(exe) if exe.exists() else shutil.which("anki-helpers")
    assert executable, "anki-helpers executable not found"

    def run(
        *args: str, url: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        full_env = {k: v for k, v in os.environ.items() if k != "API_KEY"}
        full_env["ANKI_CONNECT_URL"] = url
        full_env.update(env or {})
        return subprocess.run(
            [executable, *args],
            env=full_env,
            cwd=tmp_path,
            timeout=10,
            text=True,
            capture_output=True,
            check=False,
        )

    return run
