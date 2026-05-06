"""Run the mock server as ``python -m anki_helpers.mock_server``."""

import argparse

from .server import run_server


def main() -> None:
    """Parse CLI arguments and start the mock server."""
    parser = argparse.ArgumentParser(
        prog="anki_helpers.mock_server",
        description="Run a stateful mock for the AnkiConnect HTTP plugin.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8765, help="bind port")
    parser.add_argument(
        "--db",
        default=":memory:",
        help="SQLite database path (default: in-memory)",
    )
    parser.add_argument(
        "--seed",
        default=None,
        help="path to a JSON seed file loaded on startup",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="enable uvicorn auto-reload (development only)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        help="uvicorn log level (default: info)",
    )
    args = parser.parse_args()
    run_server(
        host=args.host,
        port=args.port,
        db_path=args.db,
        seed_file=args.seed,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
