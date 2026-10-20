# Design: fake AnkiConnect

Tier: smol · Date: 2026-10-19 · Parent: [grand plan §4.1, S1-03..S1-07](../2026-10-19-grand-plan/design.md)

## Data flow

```
client (AnkiConnect / curl) → POST / → server.Handler → FakeAnki.handle → action method → State
anki-helpers mock query Q → FakeAnki.handle(findNotes|findCards) → search.compile_query → ids
```

| # | Component | File | Role |
|---|-----------|------|------|
| 1 | `State`, `Note`, `Card`, `Model` | `fake_anki/state.py` | in-memory collection; stock models Basic / Basic (and reversed card) / Cloze; injectable `clock` |
| 2 | `load_state` / `dump_state` | same | seed JSON ↔ `State`; dump loads back identically |
| 3 | `compile_query`, `find_notes`, `find_cards` | `fake_anki/search.py` | Anki search subset; unsupported syntax → `SearchError` |
| 4 | `FakeAnki` | `fake_anki/actions.py` | v6/v4 envelope, ~50 actions, request log, fault injection, lock |
| 5 | `make_server`, `running` | `fake_anki/server.py` | stdlib `ThreadingHTTPServer`; debug endpoints `/_state` `/_log` `/_reset` `/_seed` `/_faults` |
| 6 | `mock serve`, `mock query` | `cli.py` | manual use; SIGTERM/SIGINT → `--dump-on-exit` |

## Decisions (defaults picked, differ from grand plan)

- stdlib `http.server`, not uvicorn/ASGI; no pydantic. Reason: no new runtime deps; client is still `requests`. ⚠️ revisit with S1-01/02 (`httpx`, `AnkiPort`).
- No `httpx.MockTransport` mode yet; unit tests call `FakeAnki.handle` directly (same thing without sockets).
- CLI stays Click (Typer port is S0-04).
- Seed `due` for review cards = days relative to `today`; `cardsInfo.due` reports `today + due` like Anki's day number.
- `findNotes("")` returns all notes. ⚠️ real Anki may scope an empty search to the current deck.
- `prop:ease` skips new cards. ⚠️ matches recent Anki rslib as far as known.
- `/_reset` restores the startup seed, not the last `/_seed`.

## Acceptance coverage

| Issue | AC | Covered by |
|---|---|---|
| S1-03 | shape-identical to recorded fixtures | `tests/unit/test_fake_shapes.py` vs `tests/fixtures/ankiconnect/readme_v6.json` (README examples, ⚠️ not recorded: S1-08) |
| S1-04 | duplicate add errors; `mod` bumps via injected clock | `test_fake_actions.py::test_add_note_errors`, `::test_update_bumps_mod` |
| S1-05 | media base64 round-trip; missing → `false` | `test_fake_actions.py::test_media` |
| S1-06 | e2e fixture on random port; legacy CLI works; fault injection | `tests/e2e/test_fake_server_e2e.py`; `Fault.noop` = "note open in browser" |
| S1-07 | legacy commands e2e against fake; default `--limit 5` | `test_fake_server_e2e.py` (all three commands, OpenAI via local stub), `tests/unit/test_anki_connect_vs_fake.py` |

## Not done (grand plan S1)

- S1-01/02 `AnkiPort` + httpx client; so S1-07 runs the legacy `requests` client against the fake instead of porting it onto `AnkiPort`.
- S1-08 contract suite vs real headless Anki; reference shapes come from the README until then.
- `list-red-flags` order: S1-07 says "due desc"; the command sorts by `dueQuery` ascending (overdue first). Pinned as-is in e2e; ⚠️ needs a decision.
