# Validation: manual smoke against the fake (PR #11)

Date: 2026-10-24 · Branch `ccr-dfc42be6-qs9tj1` @ `b054eac` · macOS, Python 3.14.4, zsh

Tester: Dzianis Sheka (manual, human). The tester followed the "Manual" steps in the PR #11 body exactly,
in an interactive zsh session on a fresh checkout after `uv sync`, with the default `fixtures/basic.json` seed.
The table below records the observed output of each step.

| Step | Expected | Result |
|---|---|---|
| `mock serve --port 8765 --dump-on-exit /tmp/out.json &` | banner + `export ANKI_CONNECT_URL=…` | ✅ |
| `list-deck` | Default, German, German::Vocab, Spanish | ✅ |
| `list-red-flags` (default limit) | 5 cards: Hund, Katze, Hola×2, laufen | ✅ due 2026-10-23 → 10-29, ascending |
| `POST /_faults {"action":"updateNoteFields","noop":true,"times":1}` | `{"ok": true}` | ✅ |
| `updateNoteFields` note 1001 `Back=puppy` | `{"result": null, "error": null}` | ✅ success reported |
| `notesInfo` note 1001 | `Back` still `dog` | ✅ noop fault confirmed (S1-06) |
| `kill %1` | `State written to /tmp/out.json` | ❌ printed `Aborted!`, exit 1, no file |

## Findings

1. **`--dump-on-exit` lost on `kill %1` (bug).** In an interactive shell, `kill %1` sends SIGTERM to the
   whole job process group, so both `uv` and the Python child get it. `uv` then forwards the signal to the
   child too. The likely result is a second `KeyboardInterrupt` raised by the `stop` handler while the
   `finally:` block in `cli.py` `serve` is running. That aborts the dump, and Click reports `Aborted!`.
   Follow-up check by Claude Code, separate from the manual run: SIGTERM sent to the `uv` PID alone
   (non-interactive shell) works: exit 0, `State written to …`. The process-group case could not be
   reproduced in its sandbox, so the root cause above is unconfirmed.
   Possible fix: on the first signal, reset the handlers to `SIG_IGN`, or set a flag and call
   `httpd.shutdown()` instead of raising. Add an e2e test that sends the signal to the process group.
2. **Cloze note shows twice in `list-red-flags`.** Both cards (c1, c2) render as the same raw
   `{{c1::Hola}}, ¿cómo {{c2::estás::verb}}?` text. The output is correct per card, but hard to read.
   Rendering the cloze for each card, or showing the card ordinal, would help. This feeds the open
   "readability with the cloze note" item.
3. Sort order is ascending by due, as the PR describes. Decided: keep it (see Decisions below).

## `cardsInfo` extras vs real Anki

2026-10-24: checked by Claude Code against Dzianis Sheka's running Anki + AnkiConnect (API version 6),
using only read actions (`findCards "flag:1"`, then `cardsInfo` on 3 cards).

- `factor` (2500, 1700, 1550) and `flags` (1, 1, 1) are present, so `EXTRA_KEYS` in `test_fake_shapes.py` is correct.
- Real keys = README keys + `factor`, `flags`, `nextReviews`. The fake returns every real key except
  `nextReviews`. No key in the fake is missing from the real response, and the shared keys have the same types.
- `nextReviews` is not modelled in the fake. The legacy commands don't use it, so it is left for S1-08.

## Decisions (Dzianis Sheka, 2026-10-24)

- `list-red-flags` order: keep ascending by due (most urgent first). The S1-07 AC wording and the docstring should say "asc".
- Keep the README-derived `readme_v6.json` as the reference shapes until S1-08 records real ones.
