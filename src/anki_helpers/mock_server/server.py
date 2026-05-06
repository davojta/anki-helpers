"""FastAPI application that exposes the AnkiConnect-compatible HTTP API.

The dispatcher accepts the AnkiConnect envelope on ``POST /`` and routes the
``action`` field to a registered handler from :mod:`handlers`. A handful of
non-AnkiConnect routes under ``/admin`` make it easy for tests to reset and
seed the mock database.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import handlers as _handlers_module  # noqa: F401  (registers handlers)
from .handlers import HANDLERS
from .state import State

LOGGER = logging.getLogger("anki_helpers.mock_server")


class Envelope(BaseModel):
    """Pydantic model for the AnkiConnect request envelope."""

    action: str
    version: int = 6
    params: Dict[str, Any] = Field(default_factory=dict)
    key: Optional[str] = None


class MockAnkiConnectServer:
    """Wraps a :class:`State` and exposes a FastAPI app over it."""

    def __init__(self, state: Optional[State] = None) -> None:
        """Initialize the FastAPI app.

        Args:
            state: An existing :class:`State` to share with tests. When
                omitted, a fresh in-memory state is created.
        """
        self.state = state or State(":memory:")
        self.app = FastAPI(title="anki-helpers mock AnkiConnect")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        """Attach the AnkiConnect endpoint and admin helpers to the app."""
        app = self.app
        state = self.state

        @app.get("/", response_class=PlainTextResponse)
        async def liveness() -> str:
            """Return the AnkiConnect-style banner so probes succeed."""
            return "AnkiConnect v.6"

        @app.post("/")
        async def dispatch(request: Request) -> JSONResponse:
            """Route an AnkiConnect envelope to the appropriate handler."""
            return await self._dispatch(request)

        @app.post("/admin/reset")
        async def admin_reset() -> Dict[str, str]:
            """Wipe the mock database back to an empty default state."""
            state.reset()
            return {"status": "ok"}

        @app.post("/admin/seed")
        async def admin_seed(payload: Dict[str, Any]) -> Dict[str, Any]:
            """Load decks/models/notes from a JSON payload (see State.load_seed)."""
            state.load_seed(payload)
            return {
                "status": "ok",
                "decks": [
                    row["name"]
                    for row in state.db.execute("SELECT name FROM decks ORDER BY id")
                ],
                "noteCount": state.db.execute(
                    "SELECT COUNT(*) AS c FROM notes"
                ).fetchone()["c"],
            }

        @app.post("/admin/load-seed-file")
        async def admin_load_seed_file(payload: Dict[str, str]) -> JSONResponse:
            """Load a seed payload from a JSON file path on the server."""
            path = payload.get("path")
            if not path:
                return JSONResponse(
                    {"status": "error", "error": "missing 'path'"},
                    status_code=400,
                )
            data = json.loads(Path(path).read_text())
            state.load_seed(data)
            return JSONResponse({"status": "ok"})

    async def _dispatch(self, request: Request) -> JSONResponse:
        """Decode the envelope, run the handler, and emit the response."""
        body = await request.body()
        try:
            envelope = Envelope.model_validate_json(body)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("rejecting malformed body: %s", exc)
            return JSONResponse({"result": None, "error": f"bad request: {exc}"})
        handler = HANDLERS.get(envelope.action)
        if handler is None:
            LOGGER.info("unsupported action: %s", envelope.action)
            return JSONResponse({"result": None, "error": "unsupported action"})
        try:
            result = handler(envelope.params, self.state)
        except ValueError as exc:
            LOGGER.info("handler %s rejected: %s", envelope.action, exc)
            return JSONResponse({"result": None, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("handler %s crashed", envelope.action)
            return JSONResponse({"result": None, "error": str(exc)})
        return JSONResponse({"result": result, "error": None})


def create_server(db_path: str = ":memory:") -> MockAnkiConnectServer:
    """Build a :class:`MockAnkiConnectServer` backed by ``db_path``.

    Args:
        db_path: Filesystem path or ``:memory:`` for an in-memory database.

    Returns:
        A configured :class:`MockAnkiConnectServer`.
    """
    return MockAnkiConnectServer(State(db_path))


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    db_path: str = ":memory:",
    seed_file: Optional[str] = None,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """Start the mock server using uvicorn.

    Args:
        host: Bind host.
        port: TCP port.
        db_path: SQLite database path; ``:memory:`` for ephemeral state.
        seed_file: Optional path to a JSON seed file (see :meth:`State.load_seed`).
        reload: Enable uvicorn auto-reload (development only).
        log_level: uvicorn log level.
    """
    import uvicorn  # local import keeps optional dep lazy

    server = create_server(db_path)
    if seed_file:
        server.state.load_seed(json.loads(Path(seed_file).read_text()))
    uvicorn.run(
        server.app,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )
