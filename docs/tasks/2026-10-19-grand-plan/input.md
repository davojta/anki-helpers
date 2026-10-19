# Grand plan: modernize anki-helpers

## Input

Source: Claude research chat <https://claude.ai/share/90177d92-ce37-485b-bc7e-eecfa133027d>.
Full report: [design.md](design.md).

### Requirements (as numbered in the report)

1. AnkiConnect client + fake, so everything is testable without a live Anki.
2. Markdown data model + bidirectional sync with Anki.
3. HTML docs site + exploration pages.
4. `docs/llm-wiki` following Karpathy's "LLM wiki" pattern.
5. (Not referenced in the report; likely the issue → PR Claude Code workflow.)
6. MCP server for inspecting/debugging Anki and the vault.
7. LLM card generation from books/topics, history-safe regeneration.
8. Online UI + Obsidian vault sync + homelab hosting.

### Current state

- Poetry + unittest, Click CLI with `list-deck`, `list-red-flags`,
  `get-examples-for-red-flags-cards` (OpenAI hard-coded).
- Needs a running Anki desktop with AnkiConnect; no fake, no data model,
  no sync, no docs/MCP/UI.

### Constraints

- Work is split into small issues (≤ ~400 LOC, one PR each), labelled
  `agent` + `stage:Sx`, implemented by Claude Code via `claude.yml`.
- Tests never touch a real Anki or the network (`real_anki` marker only in
  `tests/contract/`).
- AnkiConnect is never exposed publicly.
- No Anki note deletion without explicit `--prune` / `confirm=True`.

### Known gaps in the research

- Repo files, the 4 open PRs, and `project-templates/python-cli` were not
  read. S0-01 does the inventory.
- AnkiConnect "API v1" (JSON-RPC, Anki 26.08+) is reported by a third-party
  PR only; plan targets v6 behind `AnkiPort` (D2).
- Material for MkDocs end-of-life date conflicts between sources (D5).
