# Design: ruff, pyright, pytest

Tier: medium · Date: 2026-10-19 · Proposal: [proposal.md](proposal.md)

## Data flow

Gate:

```
dev / pre-commit / CI → [make check] → [ruff check + format --check] → [pyright] → [pytest unit + e2e] → pass / fail
```

e2e test:

```
pytest → [anki_stub fixture] → [subprocess anki-helpers] → [AnkiConnect(url from ANKI_CONNECT_URL)] → [stub HTTP server] → stdout / stderr
```

| # | Component | In | Transform | Out |
|---|-----------|----|-----------|-----|
| 1 | `Makefile` `check` (new) | repo | runs `lint`, `typecheck`, `test` in order, stops on first failure | exit code |
| 2 | `tests/e2e/conftest.py::anki_stub` (new) | per action: fixed result or `Callable[[params], result]` | starts `ThreadingHTTPServer` on `127.0.0.1:0`, answers `{"result": ..., "error": None}`, records requests | `AnkiStub` (url, requests) |
| 3 | `tests/e2e/conftest.py::run_cli` (new) | CLI args, stub url | runs `<venv>/bin/anki-helpers` with `ANKI_CONNECT_URL` set, `cwd=tmp_path` (no dev `.env` leaks in), `timeout=10` (`requests.post` has none, a stuck stub must not hang CI) | `subprocess.CompletedProcess[str]` |
| 4 | `AnkiConnect.__init__` | `url: str \| None` | `url` → else `ANKI_CONNECT_URL` (shell env, then `.env`) → else `http://localhost:8765` | client |

## Types: data flow

```python
@dataclass
class AnkiStub:  # tests/e2e/conftest.py, new
    url: str                          # http://127.0.0.1:<port>
    responses: dict[str, Any]         # action → result, or Callable[[dict[str, Any]], Any] for param-dependent answers
    requests: list[dict[str, Any]]    # bodies received, for asserts

DEFAULT_URL = "http://localhost:8765"  # src/anki_helpers/anki_connect.py, new
```

TypedDicts / pydantic for AnkiConnect payloads: not here (S1).

## Types: critical path

| Symbol | File | Before | After |
|--------|------|--------|-------|
| `AnkiConnect.__init__` | `src/anki_helpers/anki_connect.py` | `(self, url: str = "http://localhost:8765")` | `(self, url: str \| None = None) -> None` |
| `AnkiConnect._invoke` | same | `(self, action: str, **params) -> Any` | `(self, action: str, **params: Any) -> Any` |
| `get_deck_names` etc. | same | `List[str]`, `Dict[str, Any]` | `list[str]`, `dict[str, Any]` (UP006) |
| `load_dotenv` | `src/anki_helpers/cli.py` | `()`, called only in `get_examples_for_red_flags_cards` ✅ `cli.py:179` | `() -> None`, called once in the `cli` group callback, so `.env` applies to every command |
| `cli`, `version`, `hello_world`, `list_deck` | same | `()` | `() -> None` |
| `list_red_flags` | same | `(limit)` | `(limit: int) -> None` |
| `get_examples_for_red_flags_cards` | same | `(output_dir, limit)` | `(output_dir: str, limit: int \| None) -> None` ✅ `--limit` default `None` |

> **[HITL-1]** Check: `ANKI_CONNECT_URL` name and precedence (arg → shell env → `.env` → default). Why: new public config; S1 `AnkiPort` will build on it. How: `src/anki_helpers/anki_connect.py`, `.env.example`, README "Configuration".

Out of scope: replacing the hand-written `load_dotenv` with the unused `python-dotenv` dependency ✅ (`pyproject.toml`).

Rule: type-only fixes in `src/`. Exceptions: `raise ... from e` (B904), `zip(..., strict=True)` (B905, ⚠️ AnkiConnect `getIntervals` returns one value per card), `f"{e!s}"` (RUF010), `ANKI_CONNECT_URL` + `load_dotenv()` in `cli` group.

> **[HITL-2]** Check: `src/` diff is types, lint fixes and the URL/`.env` change only. Why: pyright strict tempts casts and rewrites that change output. How: `git diff src/`, `make test`.

## Config

`pyproject.toml`:

```toml
[dependency-groups]
dev = ["pre-commit", "ruff", "pyright", "pytest", "pytest-cov", "types-requests"]  # mypy removed

[tool.ruff]
line-length = 88              # = black today, no reformat churn
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "D", "SIM", "RUF", "PT"]
pycodestyle.max-line-length = 120   # = flake8 today
pydocstyle.convention = "google"

[tool.pyright]
include = ["src", "tests"]
strict = ["src"]
typeCheckingMode = "standard"
pythonVersion = "3.14"
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
markers = ["e2e: runs the installed CLI against the stub AnkiConnect"]
```

Drop `[tool.flake8]`.

`.pre-commit-config.yaml`: remove black, isort, flake8, mypy. Add `repo: local` hooks
`ruff-check` (`ruff check --fix`), `ruff-format`, `pyright` (all `uv run`, `language: system`,
pyright `pass_filenames: false`). Versions come from `uv.lock`, one source.
Keep `pre-commit-hooks` and `conventional-pre-commit`. `name-tests-test`: add
`args: [--pytest-test-first]` ⚠️ (stub lives in `conftest.py` so no non-test module).

`Makefile` (new):

```make
.PHONY: lint typecheck test test-unit test-e2e check fmt

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest --cov=anki_helpers --cov-report=term-missing

test-unit:
	uv run pytest -m "not e2e"

test-e2e:
	uv run pytest -m e2e

check: lint typecheck test

fmt:
	uv run ruff check --fix .
	uv run ruff format .
```

`ci.yml`: `uv sync --locked` → `make check` →
`SKIP=ruff-check,ruff-format,pyright uv run pre-commit run --all-files` (generic hooks only;
ruff and pyright already ran in `make check`). Hook ids in `.pre-commit-config.yaml` must match
the `SKIP` list.

## Tests layout

```
tests/
  conftest.py              # shared: mock_anki fixture (patches anki_helpers.cli.AnkiConnect)
  unit/
    test_cli.py            # from cli_test.py; no sys.path hack; OpenAI mock via MagicMock
    test_anki_connect.py   # requests.post patched
    test_clean_html.py     # parametrized clean_html_content
  e2e/
    conftest.py            # AnkiStub, anki_stub, run_cli
    test_cli_e2e.py        # pytestmark = pytest.mark.e2e
```

`tests/cli_test.py`: deleted (moved). ✅ project installed editable by `uv sync`, so imports work.

## Test scenarios

**T1 positive: list-deck e2e**
- Given: stub `deckNames → ["B", "A"]`.
- Action: `anki-helpers list-deck`.
- Result: exit 0; stdout `Available decks:\n  • A\n  • B`; stub got one `deckNames`, `version: 6`.

**T2 positive: list-red-flags e2e with limit**
- Given: stub answers `findNotes` (`flag:1` → 3 ids, due queries → `[]`), `findCards`, `cardsInfo`, `getIntervals`, `notesInfo`.
- Action: `anki-helpers list-red-flags --limit 2`.
- Result: exit 0; 2 cards printed, cleaned of HTML; third absent.

**T3 negative: no decks**
- Given: stub `deckNames → []`.
- Action: `anki-helpers list-deck`.
- Result: exit 0; stdout `No decks found.`

**T4 error handling: Anki down (e2e)**
- Given: `ANKI_CONNECT_URL` points to a closed port.
- Action: `anki-helpers list-deck`.
- Result: stderr has `Failed to connect to AnkiConnect` and the "Make sure Anki is running" hint; exit 0 ✅ (current behavior, not changed here).

**T5 error handling: AnkiConnect error field (unit)**
- Given: `requests.post` returns `{"result": null, "error": "boom"}`.
- Action: `AnkiConnect().get_deck_names()`.
- Result: `AnkiConnectError("AnkiConnect error: boom")`. Network failure: `AnkiConnectError` with `__cause__` = the `RequestException`.

**T6 positive: URL precedence (unit)**
- Given: arg; shell env; `.env` only (via `cli`, `tmp_path` cwd); shell env and `.env` both set; none.
- Action: `AnkiConnect(url)` / `AnkiConnect()`.
- Result: `.url` = arg; shell value; `.env` value; shell value (`.env` never overrides, ✅ `cli.py:31`); `http://localhost:8765`.

**T7 gate: make check**
- Given: clean tree.
- Action: `make check`.
- Result: ruff 0 findings, pyright 0 errors, all tests pass.

## HITL

> **[HITL-1]** Check: `ANKI_CONNECT_URL` name and precedence. Why: new public config. How: `anki_connect.py`, `.env.example`, README.
>
> **[HITL-2]** Check: `src/` diff is types, lint fixes and the URL/`.env` change only. Why: silent behavior change. How: `git diff src/`, `make test`.

## File map

| File | Change | Why |
|------|--------|-----|
| `pyproject.toml` | mod | dev deps, ruff/pyright/pytest config, drop flake8 |
| `uv.lock` | mod | new dev deps |
| `.pre-commit-config.yaml` | mod | ruff + pyright local hooks, drop black/isort/flake8/mypy |
| `Makefile` | new | `lint`, `typecheck`, `test*`, `check`, `fmt` |
| `.github/workflows/ci.yml` | mod | `make check` |
| `src/anki_helpers/anki_connect.py` | mod | types, `DEFAULT_URL`, env URL, B904/B905/RUF010 |
| `src/anki_helpers/cli.py` | mod | types, ruff fixes, `load_dotenv()` moved to `cli` group |
| `src/anki_helpers/prompts/examples_for_red_cards.py` | mod | ruff fixes only if flagged |
| `tests/cli_test.py` | del | moved to `tests/unit/test_cli.py` |
| `tests/conftest.py` | new | shared fixtures; autouse `isolated_env`: `monkeypatch.chdir(tmp_path)`, then `with patch.dict(os.environ):` pop every `.env.example` key (`API_KEY`, `ANKI_CONNECT_URL`) and `yield`. `load_dotenv` writes `os.environ` directly; `patch.dict` restores the whole env after each test. ✅ tested: `monkeypatch.delenv(k, raising=False)` on an unset key does not undo a later set |
| `tests/unit/test_cli.py` | new | CLI unit tests |
| `tests/unit/test_anki_connect.py` | new | client unit tests (T5, T6) |
| `tests/unit/test_clean_html.py` | new | `clean_html_content` cases |
| `tests/e2e/conftest.py` | new | `AnkiStub`, `anki_stub`, `run_cli` |
| `tests/e2e/test_cli_e2e.py` | new | T1–T4 |
| `CLAUDE.md` | mod | commands, code-quality section, Environment: `ANKI_CONNECT_URL` |
| `README.md` | mod | test section (drop unittest), "Configuration": `.env` keys |
| `.env.example` | new | `API_KEY=`, `ANKI_CONNECT_URL=http://localhost:8765`; committed (`.gitignore` ignores only `.env` ✅) |

## Stages

1. Tooling: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `Makefile`. Done when: `make lint` and `make typecheck` run (failures expected).
2. Lint: `ruff check --fix`, `ruff format`, manual B904/B905. Done when: `make lint` green, old tests pass.
3. Types: `src/` to pyright strict, `ANKI_CONNECT_URL` + `.env` loading in `cli`, `.env.example` [HITL-1, HITL-2]. Done when: `make typecheck` green, old tests pass.
4. Tests: unit + e2e layout, T1–T6. Done when: `make test` green, `make test-e2e` runs ≥4 tests.
5. CI + docs: `ci.yml`, `CLAUDE.md`, `README.md`. Done when: `make check` green locally and in CI.
