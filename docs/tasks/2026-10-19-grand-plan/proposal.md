# Proposal

Full detail (designs, schemas, CI YAML, every issue's acceptance criteria):
[design.md](design.md). Section refs below (§) point there.

## Approach

Rebuild on uv + hatchling, ruff, mypy --strict, pytest, Typer + Rich, httpx,
pydantic v2 (§2). Everything plugs into two foundations:

1. **Fake AnkiConnect** (§4.1) — stateful v6 emulator behind an `AnkiPort`
   protocol; runs as `httpx.MockTransport`, as a uvicorn server, and as
   `anki-helpers mock serve`. Contract suite keeps it in parity with a real
   headless Anki container.
2. **Markdown vault** (§4.2) — one file = one note, directory = deck, YAML
   front matter with `uid`, `model`, `tags`, and sync-owned `anki:`
   (`note_id`, `mod`, `md_hash`, `html_hash`).

## Stages

| Stage | Goal | Depends on | Issues |
|-------|------|------------|--------|
| S0 Bootstrap | Agent-ready repo, green CI, CLAUDE.md, SPEC.md, llm-wiki skeleton | — | S0-01..07 |
| S1 AnkiConnect client + fake | Everything testable without Anki | S0 | S1-01..08 |
| S2 Markdown data model | Lossless, validated vault model | S0 (parallel with S1) | S2-01..07 |
| S3 Bidirectional sync | Safe, idempotent MD↔Anki | S1, S2 | S3-01..08 |
| S4 Docs site + exploration | Published HTML docs (Zensical) | S0; refreshed after each stage | S4-01..06 |
| S5 MCP server | Agent can inspect/debug (FastMCP, stdio) | S1–S3 | S5-01..05 |
| S6 LLM generation | Book/topic → reviewed cards, history-safe regen | S2, S3 (S6-01..05 only S2) | S6-01..09 |
| S7 Web UI + vault + homelab | Browser authoring (FastAPI + HTMX) | S3, S6 | S7-01..07 |

Order: S0 → {S1 ∥ S2} → S3 → {S4 (continuous), S5} → S6 → S7. 57 issues total.

Each stage becomes its own ledger task (`parent: 2026-10-19-grand-plan`);
each issue is filed on GitHub with labels `agent` + `stage:Sx`.

## Design defaults (assumptions A1–A9, §9)

- **Conflicts:** both sides changed → write `note.conflict.md`, touch
  nothing, exit 3. Resolve with `sync --prefer local|anki|newer` or `resolve`.
- **Deletions:** deleted file → tag `anki-helpers::orphan` + suspend;
  `deleteNotes` only with `--prune`.
- **Regeneration:** match by `card_key`, update fields on the same
  `note_id` (keeps review history); unmatched → `status: retired`.
- **Drafts:** generated cards start `status: draft`, excluded from sync
  until `gen promote`.
- **Hosting:** Markdown in git is the source of truth; the web UI only
  commits; desktop runs `anki-helpers sync`. Headless-Anki hub on the
  homelab is optional (D7). AnkiConnect never published.
- **LLM:** Claude by default via `CardGenerator`; `FakeProvider` in tests;
  OpenAI optional.

## Definition of Done (per issue, §6)

1. Acceptance criteria met, each with a test.
2. `make check` green locally and in CI.
3. Behavior change → docs page; new decision → ADR.
4. Append to `docs/llm-wiki/wiki/log.md`, update touched wiki pages.
5. No secrets; no TODO without a linked issue.

## Open decisions (§10)

- [ ] D1 mypy vs pyright
- [ ] D2 AnkiConnect v6 only vs adding JSON-RPC v1 adapter
- [ ] D3 Conflict default: no-overwrite + conflict file vs LWW
- [ ] D4 Standalone FastMCP vs official `mcp` SDK `MCPServer`
- [ ] D5 Zensical vs pinned Material/MkDocs 1.x
- [ ] D6 Multi-card-per-file support (deferred)
- [ ] D7 Homelab hub topology vs desktop-only
- [ ] D8 License: keep Unlicense?

## Risks (§11)

API drift, fake/real divergence, lossy HTML↔MD round-trip, AnkiWeb
full-sync conflicts with a hub, low-quality LLM cards, prompt injection via
issues, dependency churn, secrets exposure. Mitigations in §11.
