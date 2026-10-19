# anki-helpers modernization: staged plan for Claude Code (issue → PR software factory)

**Bottom line:** Rebuild anki-helpers as a uv/ruff/mypy/pytest/Typer project. The first piece to build is an in-process **fake AnkiConnect**: a stateful v6 emulator that also runs as an HTTP server. Next comes a **one-note-per-file Markdown + YAML front-matter model** with three-way hash/mod-time sync. Everything else plugs into those two pieces: the MCP server, LLM generation, the web UI, the docs, and the LLM wiki. The plan has 8 stages (S0–S7) and roughly 50 small `agent` issues.

## TL;DR
- **Order:** S0 bootstrap (tooling, CI, CLAUDE.md, SPEC.md, llm-wiki skeleton) → S1 AnkiConnect client + fake/mock server, S2 Markdown data model (these two run in parallel) → S3 bidirectional sync → S4 docs site → S5 MCP server → S6 LLM card generation → S7 web UI + Obsidian vault sync + homelab deploy.
- **Key design defaults (assumptions):**
  - Directory = deck; one file = one Anki note.
  - Front matter stores `note_id`, Anki `mod`, and the hashes from the last sync.
  - On conflict, nothing is overwritten. A `.conflict.md` sibling file is written instead.
  - Deletions never propagate by default; notes are tagged and suspended instead.
  - LLM regeneration updates fields on existing note IDs, so review history survives.
- **Hosting:** Real AnkiConnect is a localhost desktop add-on. Treat Markdown in git as the source of truth. Desktop CLI sync is the baseline path. An optional headless-Anki container on the homelab, synced via AnkiWeb, lets the online UI reach Anki. Never expose AnkiConnect publicly.

---

## 1. Current state (inspected)

**davojta/anki-helpers** (public, Unlicense, 12 commits, 4 open PRs):
- Layout: `src/`, `tests/`, `.github/workflows/`, `CLAUDE.md`, `todo.md`, `.pre-commit-config.yaml`, `.markdownlint.json`, `poetry.lock`, `pyproject.toml`.
- Tooling: Poetry. Tests use `unittest` (`poetry run python -m unittest discover tests`; known test `tests/cli_test.py::test_version`). pytest is described as optional.
- Features:
  - `list-deck`
  - `list-red-flags [--limit N]`: notes tagged `marked`, sorted by due date descending, default 5.\[1\]
  - `get-examples-for-red-flags-cards [--limit N] OUTPUT_DIR`: writes `input-words.md`, calls OpenAI GPT-4o, saves `results.md`. Needs `openai`, `python-dotenv`, and `API_KEY` in `.env`.\[1\]
- Runtime requirement: "Anki must be running" with AnkiConnect installed.\[1\]
- **Gaps:**
  - No AnkiConnect fake, so tests can't exercise Anki without a live desktop.
  - No data model or sync.
  - LLM provider is hard-coded (OpenAI).
  - No docs site, MCP server, or UI.
  - Poetry + unittest is behind current practice.
- **Not inspected:** individual file contents (`pyproject.toml`, `CLAUDE.md`, `todo.md`, `src/**`, the 4 open PRs). The fetch tooling blocked them. S0-01 makes the agent inventory these itself.

**davojta/project-templates/python-cli:** not accessible (robots-blocked). **Decision:** adopt it conditionally. If it already uses uv + ruff + a type checker + pytest + Typer/Click + pre-commit, use it as the copier source. Otherwise use the stack in §2. The template's own conventions (e.g. Makefile vs justfile) override §2 where they don't conflict. *(Assumption.)*

## 2. Target stack (decision + justification)

| Concern | Choice | Why / alternative |
|---|---|---|
| Python | 3.12 only (CI), `requires-python >=3.12` | Keeps the CI matrix minimal. |
| Env/packaging | **uv** + `pyproject.toml` (PEP 621), `uv.lock`, hatchling backend | Fast, one tool for venv, lock, and run. Replaces Poetry. |
| Lint/format | **ruff** (`check` + `format`) | Replaces flake8/black/isort. |
| Types | **mypy --strict** on `src/` | Pyright is the alternative; pick one. *Open decision D1.* |
| Tests | **pytest**, pytest-cov, pytest-httpx or an `httpx.MockTransport` fixture, hypothesis (for the parser round-trip) | Replaces unittest. |
| CLI | **Typer** (Click underneath) + Rich | Typed signatures, matches pydantic models. |
| HTTP | **httpx** (sync + async) | One client for CLI, MCP, and web. |
| Models | **pydantic v2** | Front matter schema, AnkiConnect payloads, LLM structured output. |
| Markdown | `python-frontmatter`/`ruamel.yaml` (round-trip-safe), `markdown-it-py` (MD→HTML), `markdownify` (HTML→MD on pull) | |
| Hooks | pre-commit: ruff, ruff-format, mypy, markdownlint, end-of-file/trailing-ws | Keep the existing markdownlint config. |
| Scaffolding | **copier** (if a template is used) | Supports `copier update`, which cookiecutter does not. |
| Task runner | `Makefile` with `make check` = lint + type + test | Gives the agent one command to run. |

## 3. Proposed repo layout

```
anki-helpers/
├─ pyproject.toml  uv.lock  Makefile  .pre-commit-config.yaml
├─ CLAUDE.md  SPEC.md  README.md  LICENSE
├─ .github/
│  ├─ workflows/{ci.yml, claude.yml, real-anki.yml}
│  └─ ISSUE_TEMPLATE/agent-task.yml
├─ src/anki_helpers/
│  ├─ cli/                 # typer app: deck, notes, sync, gen, mock, mcp, web
│  ├─ ankiconnect/         # client.py, models.py, errors.py, protocol.py (AnkiPort)
│  ├─ fake_anki/           # state.py, actions.py, server.py, fixtures/
│  ├─ notes/               # schema.py, parse.py, render.py, hashing.py, media.py, cloze.py
│  ├─ sync/                # plan.py (diff), apply.py, conflicts.py, state.py
│  ├─ gen/                 # ingest/{epub,pdf,md}.py, chunk.py, providers/{base,anthropic,fake}.py, prompts/, validate.py, regen.py
│  ├─ mcp_server/          # server.py (tools/resources)
│  ├─ web/                 # FastAPI app, templates/ (Jinja+HTMX), vault/ (git backend)
│  └─ legacy/              # ported red-flag commands
├─ tests/
│  ├─ unit/  e2e/  contract/   # contract = real headless Anki (marker: real_anki)
│  └─ fixtures/{vaults,anki_states,books}/
├─ docs/
│  ├─ index.md  architecture.md  data-model.md  sync.md  cli.md  mcp.md  generation.md  web.md
│  ├─ exploration/{ankiconnect-api.md, existing-tools.md, obsidian-sync.md, llm-flashcards.md}
│  ├─ adr/NNNN-*.md
│  └─ llm-wiki/{SCHEMA.md, raw/, wiki/{index.md, log.md, concepts/, entities/, sources/, decisions/}}
├─ mkdocs.yml               # read by Zensical (or MkDocs) for the HTML site
├─ deploy/{compose.yaml, Caddyfile.example}
└─ scripts/{wiki_lint.py, record_contract.py}
```

## 4. Key designs

### 4.1 AnkiConnect client + fake (Req 1)

**API facts used:**
- Transport: POST JSON `{"action","version":6,"params"}` to `http://127.0.0.1:8765`. Reply is `{"result","error"}`. If `version` is omitted, the call falls back to v4 semantics (result only).\[2\]
- Actions the fake must support:
  - Deck/model/version: `version`, `deckNames`, `createDeck`, `modelNames`, `modelFieldNames`
  - Search/read: `findNotes`, `notesInfo` (returns `mod`), `notesModTime`
  - Write: `addNote`, `addNotes`, `canAddNotes(WithErrorDetail)`, `updateNoteFields`, `updateNote` (fields first; not rolled back if tags fail),\[2\] `addTags`, `removeTags`, `deleteNotes`
  - Cards/media/other: `findCards`, `cardsInfo`, `suspend`, `storeMediaFile`, `retrieveMediaFile`, `multi`, `sync`
- **Caveat (unverified, third-party):** a 12 Oct 2026 yanki-connect PR reports that AnkiConnect 26.10.11.x introduced a new JSON-RPC "API v1", moved the v6 docs to `API_LEGACY.md`, and requires Anki 26.08+. The same PR says v6 is "still fully supported".\[3\] **Decision:** target v6 behind an `AnkiPort` protocol, so a v1 adapter can be added later (D2).

**Design:**
- `AnkiPort` (typing.Protocol) with the methods the app needs. `AnkiConnectClient(httpx)` implements it, plus `multi` batching and typed errors.
- `fake_anki.State`: in-memory collection (decks, models with fields/templates incl. Basic, Basic (and reversed), Cloze; notes with `mod`; cards; media; tags). The clock is injectable so `mod` is deterministic.
- Each action handler validates params against pydantic models and returns AnkiConnect-shaped errors. Error strings are copied from the real add-on where known, e.g. duplicate → error; `model was not found: X`.
- Three ways to run the same fake:
  1. `httpx.MockTransport` (unit tests, no sockets).
  2. ASGI/uvicorn server on a random port (e2e).
  3. CLI `anki-helpers mock serve --port 8765 --seed fixtures/x.json --dump-on-exit`, for manual use, the MCP server, and the web UI in dev.
- Debug endpoints: `GET /_state`, `POST /_reset`, `POST /_seed`. Fault injection: latency, `collection is not available`, and "note open in browser" for the `updateNoteFields` no-op caveat.
- **Contract parity:**
  - `tests/contract/` runs the same scenario suite against (a) the fake and (b) a real headless Anki container, marker `real_anki`.
  - Candidate images: `thisisnttheway/headless-anki` (AnkiConnect preinstalled, `QT_QPA_PLATFORM=offscreen`, port 8765)\[4\] and `ghcr.io/ankimcp/headless-anki` (amd64/arm64; AnkiConnect via the addons variant, which is "local only").\[5\]
  - `scripts/record_contract.py` records real responses into fixtures. CI then diffs fake vs recorded output.
- **Alternatives considered:**
  - `glechic/anki-connect-server`: a headless, AnkiConnect-compatible server on direct collection access.\[6\] Useful as a second contract target; third-party, so verify.
  - Direct `anki` Python package collection access: rejected as the primary path. It bypasses the add-on users actually run, and collection locking conflicts with a running desktop. Possible later as an offline backend behind `AnkiPort`.

### 4.2 Markdown data model (Req 2)

**Prior art → choices:**

| Tool | ID storage | Direction | Lesson |
|---|---|---|---|
| Obsidian_to_Anki | ID line/HTML comment after the note block; file hashes; frontmatter option in the Kai fork | MD→Anki (+ explicit DELETE marker) | Inline IDs are fragile; frontmatter is cleaner.\[7\]\[8\] |
| inka/inka2 | HTML comment with ID; hashing for performance | MD→Anki only ("Sync from Anki… won't be [implemented]… many pitfalls") | Pull is hard; design it explicitly.\[9\]\[10\] |
| Yanki | Folder→deck, one Obsidian note = one Anki note, ID saved after first sync; namespace isolates managed notes | MD→Anki (+ AnkiWeb sync) | Folder = deck, one-note-per-file. |
| ankdown | ID = filename + index | MD→apkg | Positional IDs break review history. Avoid.\[11\] |
| Anki Card Link | Writes the ID only after Anki returns noteId; on failure leaves MD unchanged | MD→Anki | Write-back ordering. |
| whereistejas design doc | `anki_id`, `anki_mod` in frontmatter; LWW on `mod`; tag `obsidian` for orphan detection | Bidirectional | Closest to our model; we replace LWW with conflict files. |

**Schema (one file = one note; directory path = deck, `::` per level; override via `deck:`):**

```yaml
---
uid: 01JB7X...            # local ULID, never changes
model: Basic              # Basic | "Basic (and reversed card)" | Cloze | custom
deck: Books::DDIA::05     # optional override of dir-derived deck
tags: [ddia, replication]
anki:                     # written ONLY by sync
  note_id: 1714567890123
  mod: 1718377864         # notesInfo.mod at last sync
  md_hash: sha256:…       # hash of normalized fields+tags+deck+model at last sync
  html_hash: sha256:…     # hash of HTML fields as stored in Anki at last sync
source:                   # provenance (S6)
  kind: book
  id: isbn:9781449373320
  locator: "ch05 §Leaders and Followers"
  chunk_id: sha256:…
  quote: "…"              # short supporting excerpt
gen: {provider: anthropic, model: "…", prompt: cards/v3, card_key: "…", at: 2026-10-19}
status: active            # draft | active | retired
---
## Front
What does a follower do with the replication log?
## Back
Applies writes in the same order as the leader.
```

**Rules:**
- Fields are H2 sections matched to `modelFieldNames`. Unknown fields are a validation error.
- Cloze: `model: Cloze`, fields `Text`/`Back Extra`. `{{c1::…}}` passes through verbatim, and the parser checks that at least one cloze exists.
- Media: `ǃ[](assets/x.png)` → `storeMediaFile` with name `ah-<sha256[:12]>-x.png` (content-addressed, so it is idempotent). HTML gets a rewritten `‹img src>`. On pull, files missing locally are fetched via `retrieveMediaFile`. Obsidian `ǃ[[x]]` embeds are normalized on import.
- Managed notes carry the tag `anki-helpers` (namespace, for orphan detection).

### 4.3 Sync algorithm (Req 2)

`plan` is a pure function: (vault scan, `notesInfo` for managed + referenced IDs) → list of ops. `apply` executes the ops via `multi` batches. `--dry-run` prints the plan as a table/JSON.

**Change detection:**
- `L` = `md_hash(current) != anki.md_hash`
- `A` = `notesInfo.mod != anki.mod` AND `hash(html fields) != anki.html_hash`

The second check filters out mod bumps with no content change, and avoids false positives from a lossy HTML→MD round-trip.

| L | A | Action |
|---|---|---|
| no | no | noop |
| yes | no | push: `updateNote` (fields+tags); deck change → `changeDeck` |
| no | yes | pull: HTML→MD (markdownify), rewrite body, update hashes |
| yes | yes | **conflict** (default policy below) |
| new file (no note_id) | — | `canAddNotes` → `addNote`; write `note_id`/`mod`/hashes **only after** success |
| file has note_id, note missing in Anki | — | warn; `--relink` clears ID (re-add on next run) |
| managed note in Anki, no file | — | pull creates file under deck dir (`--import`), else report orphan |
| file deleted (tracked in `.anki-helpers/state.json`) | — | tag `anki-helpers::orphan` + `suspend`; `--prune` → `deleteNotes` |

**Default conflict policy (ASSUMPTION, D3):**
- Never auto-overwrite. Write `note.conflict.md` holding the Anki version and leave both sides untouched. Exit code 3.
- Resolve with `sync --prefer local|anki|newer`, or per-file `anki-helpers resolve FILE`.
- Rationale: review history lives in Anki, content intent lives in MD, and silent LWW loses edits.

**Idempotency:** a second run with no changes produces zero write ops. This is an acceptance test.

**Known hazard:** `updateNoteFields` silently doesn't update if the note is open in the Anki browser.\[2\] After a push, re-read `notesInfo`, verify the hashes, and warn.

### 4.4 MCP server (Req 6)

- **Library:** FastMCP (standalone, `fastmcp` 4.x; 4.1.1 released 18 Oct 2026). In-memory `Client(mcp)` makes testing easy.\[12\]\[13\]\[14\]
- **Churn caveat:** the official `mcp` SDK 2.x renamed its bundled `FastMCP` to `MCPServer`, so old `from mcp.server.fastmcp import FastMCP` tutorials break.\[15\] Pin major versions (D4).
- **Transport:** stdio for Claude Code (`.mcp.json` committed); streamable HTTP optional for the web UI.
- **Tools:**
  - `list_decks`, `find_notes(query, limit)`, `get_note(note_id)`
  - `sync_plan(vault_path, deck?)` (dry-run), `sync_apply(…, confirm: bool)`
  - `diff_note(path)` (MD vs Anki, field-level)
  - `validate_vault(path)`
  - `generate_cards(source, chunk?, dry_run=True)`
  - `mock_state()`, `mock_reset(seed?)` (enabled only when the backend is the fake)
- **Resources:** `anki://decks`, `anki://note/{id}`, `vault://file/{path}`, `vault://index`, `wiki://index` (docs/llm-wiki/wiki/index.md).
- **Prompts:** `review_generated_cards`, `resolve_conflict`.
- **Safety:** write tools default to dry-run. The server is configured with `ANKI_BACKEND=fake|ankiconnect` and `ANKI_URL`.
- **Prior art:** several Anki MCP servers already exist (TS: arielbk/anki-mcp, letuanvu08; Python: hbd/anki-mcp, dhkim0124 with httpx-mocked tests).\[16\]\[17\]\[18\]\[19\] This server's differentiator is vault↔Anki diff/sync and access to the fake's state.

### 4.5 LLM card generation (Req 7)

**Pipeline:** `ingest` → `chunk` → `generate` → `validate` → `write drafts` → (human/agent review) → `sync`.

- **Ingest:** EPUB (ebooklib; chapter/section from TOC), PDF (pymupdf; page-anchored locators), Markdown/URL. Each source gets a stable `source.id`.
- **Chunk:** follows structure (section boundaries), target 1.5–3k tokens. `chunk_id = sha256(source.id, locator, normalized_text)`, so an unchanged chunk keeps its ID and its cards are skipped.
- **Generate:**
  - `CardGenerator` protocol. Default `AnthropicProvider` (Claude, structured output via tool/JSON schema). `FakeProvider` (deterministic, fixture-based) is used for every test.
  - Prompt (versioned under `gen/prompts/`) encodes the SuperMemo rules: minimum information principle, cloze for lists/sets, no set enumeration, concise wording, context cues, no orphan pronouns.\[20\]\[21\] Each card returns `card_key` (chunk_id + concept slug), fields, and a supporting `quote` from the chunk.
- **Validate (deterministic):**
  - Field length caps, one fact per card (heuristic: no "and" lists/multiple blanks on Basic), cloze syntax.
  - The quote must be a substring of the chunk (grounding check against hallucination).
  - Near-duplicates are dropped (normalized-text similarity against the deck).
  - **Over-generate and filter:** in an L@S '24 study, Arif, Asthana & Collins-Thompson (U. Michigan) asked GPT-3.5/4 for 15 MCQs per transcript segment and found that fewer than 20% passed all automated quality checks. Default to generating about 2× the target count, then ranking.
- **Write:** new cards go in as `status: draft` (excluded from sync until promoted, `gen promote`).
- **Regenerate without losing history:**
  - Match new candidates to existing files by `card_key`, falling back to fuzzy match on front text within the same chunk.
  - Matched → rewrite fields in the same file, keeping `note_id` → sync does `updateNote`. Review history and scheduling are preserved.
  - Unmatched old cards → `status: retired` → sync tags + suspends them; never deletes.
  - Modes: `--mode add-only|update|full` (default `update`).
- **Legacy port:** `get-examples-for-red-flags-cards` reimplemented on `CardGenerator` (Claude default, OpenAI optional extra).

### 4.6 Online UI + Obsidian vault + hosting (Req 8)

- **UI stack: FastAPI + Jinja + HTMX.** Same process and core library as the CLI; testable with `TestClient`; no JS build.
  - Streamlit/NiceGUI rejected: weaker for multi-file editing, auth, and server-rendered partials. Acceptable for a throwaway prototype.
  - Pages: vault tree, Markdown editor with live preview + front-matter form, sync plan/diff view, conflict resolver, "generate from source" wizard (upload EPUB/PDF → chunks → drafts → promote).
- **Vault sync options:**

| Option | Works headless on homelab? | Notes | Verdict |
|---|---|---|---|
| **Git repo vault** (Obsidian Git plugin on clients; UI clones/commits/pushes) | Yes | History, merge, review; matches the "wiki is a git repo" idea | **Default** |
| Shared folder (Syncthing) | Yes | No history; conflict files | Alternative |
| Obsidian Local REST API plugin (HTTPS `127.0.0.1:27124`, API key; also MCP) | No — needs Obsidian desktop running | Good for a desktop helper, not a server | Optional desktop integration\[22\]\[23\] |
| Obsidian Sync | No | No public API *(assumption from user brief; not independently verified)* | Not supported |

- **Reaching Anki from an online UI (constraint):** AnkiConnect is a desktop add-on bound to localhost. Options:
  1. **Baseline (default):** the UI only edits Markdown + commits to git. The desktop runs `anki-helpers sync` (manual/cron/launchd) against local AnkiConnect. Safe, no exposure.
  2. **Homelab hub:** a headless Anki container (AnkiConnect, port 8765 on an internal network only, `apiKey` set) logged into AnkiWeb, with the UI syncing to it and calling `sync`. Desktop and mobile get changes via AnkiWeb.
     - Risks: AnkiWeb full-sync prompts if desktop and hub diverge; one-time AnkiWeb login via VNC; container ~1.7 GB.\[24\]
  3. **Tunnel to desktop** (Tailscale, AnkiConnect bind/CORS changed + `apiKey`): works only when the desktop is on. Not recommended.
- **Hosting:** `deploy/compose.yaml` = `web` + optional `anki-hub` + Caddy. Auth via Tailscale-only access or a forward-auth proxy (Authelia/Authentik). Secrets: `ANTHROPIC_API_KEY`, git deploy key, AnkiConnect `apiKey`.

### 4.7 Docs + exploration (Req 3)

- **Tooling:**
  - Material for MkDocs is in maintenance mode: the 9.7.0 release note (11 Nov 2025) calls it "the last release of Material for MkDocs that will receive new features", and the team moved to **Zensical**, which reads `mkdocs.yml` unchanged.
  - **Conflict in sources:** GitHub releases state end of life on 5 Nov 2026; the project changelog states 5 May 2027.\[25\]\[26\]
  - **Decision:** author `mkdocs.yml` + Markdown, build with Zensical. Fallback: pinned `mkdocs-material==9.7.*` + `mkdocs<2` (D5). Publish to GitHub Pages.
- **Exploration pages (content requirements):**
  - `exploration/ankiconnect-api.md`: actions used, request/response samples recorded from the real container, error strings, quirks (`updateNoteFields` browser caveat, v4 default without `version`, `multi` result shapes, v1 JSON-RPC status).
  - `exploration/existing-tools.md`: §4.2 table expanded.
  - `exploration/obsidian-sync.md`: §4.6 table.
  - `exploration/llm-flashcards.md`: rules, prompt versions, eval results.
  - `architecture.md` (C4 context/container + AnkiPort diagram, Mermaid), `data-model.md` (front-matter JSON Schema auto-generated from pydantic), `sync.md` (state matrix, conflict policy), `adr/` (one ADR per open decision).

### 4.8 docs/llm-wiki (Req 4)

**Karpathy's pattern** (gist `llm-wiki.md`, 4 Apr 2026, described as an "idea file"):\[27\]
- **Three layers:** raw sources (immutable), the wiki (LLM-written Markdown: summaries, entity/concept pages, comparisons), and the schema (CLAUDE.md/AGENTS.md).\[27\]
- **Three operations:** ingest (the gist: "A single source might touch 10-15 wiki pages"), query (good answers get filed back as pages), lint (contradictions, stale claims, orphans, missing cross-refs).
- `index.md` is a content catalog read first on every query; per the gist this "works surprisingly well at moderate scale (~100 sources, ~hundreds of pages)" without embedding-based RAG. `log.md` is append-only with `## [YYYY-MM-DD] op | Title` entries.

**Repo instantiation:**
- `docs/llm-wiki/raw/`: AnkiConnect README snapshot, recorded API responses, tool READMEs, SuperMemo rules, issue/PR summaries. **Agent never edits.**
- `docs/llm-wiki/wiki/`: `index.md`, `log.md`, `concepts/` (sync-state-matrix, cloze, note-id-tracking), `entities/` (AnkiConnect, Obsidian_to_Anki, inka2, FastMCP…), `sources/`, `decisions/` (mirrors ADRs).
- `docs/llm-wiki/SCHEMA.md`: page template (front matter: `type`, `sources`, `updated`, `confidence`), link style `[[page]]` + relative MD links for the HTML build.
- **Workflow hooks (in CLAUDE.md):**
  - Read `wiki/index.md` before designing.
  - After finishing an issue, append to `log.md` and update affected pages.
  - When an external tool fails with a known signature, check the wiki before a second attempt.
- `scripts/wiki_lint.py` (CI) checks:
  - every wiki page is listed in the index
  - no broken links, no orphans
  - log entries are well-formed
  - `raw/` is unchanged except for additions (git diff check)

---

## 5. SPEC.md outline

1. Purpose & non-goals (no AnkiWeb API client; no Anki add-on in v1).
2. Glossary (note, card, model, deck, vault, managed note, card_key, chunk).
3. Personas & use cases (CLI user, agent via MCP, web user).
4. Functional requirements `FR-001…` grouped: Client, Fake, Model, Sync, Gen, MCP, Web, Docs, Wiki.
5. Data model (front-matter schema, field mapping, deck mapping, media naming).
6. Sync semantics (state matrix, conflict/deletion policies, idempotency, exit codes 0/1/2/3).
7. AnkiConnect contract (action subset, version, error mapping).
8. LLM generation (provider protocol, prompt versioning, validation rules, regeneration semantics).
9. Interfaces (CLI command tree; MCP tools/resources; HTTP routes).
10. Non-functional (Python 3.12, offline tests, coverage ≥85%, no network in unit tests, secrets via env).
11. Deployment (desktop, homelab compose).
12. Open decisions (D1–D8) and assumptions (A1–A9).

## 6. CLAUDE.md contents

```markdown
# anki-helpers — agent guide
## Commands
- Setup: `uv sync --all-extras --dev`
- All checks (run before every commit): `make check`  # ruff check, ruff format --check, mypy src, pytest -m "not real_anki", wiki_lint
- Single test: `uv run pytest tests/unit/test_x.py::test_y -q`
- Fake Anki: `uv run anki-helpers mock serve --port 8765 --seed tests/fixtures/anki_states/basic.json`
- Docs: `uv run zensical serve`
## Source of truth
- Read SPEC.md and docs/llm-wiki/wiki/index.md before designing. SPEC wins over code; flag conflicts in the PR.
## Conventions
- src layout, package `anki_helpers`; typed (mypy --strict); pydantic v2 models at boundaries.
- All Anki access goes through `AnkiPort`. Never call httpx to AnkiConnect outside `ankiconnect/`.
- Tests never touch a real Anki or network. Use the `fake_anki` fixtures / `FakeProvider`.
- Real-Anki tests: marker `real_anki`, only in tests/contract/.
- No deletion of Anki notes anywhere without an explicit `--prune`/`confirm=True` path + test.
- Conventional Commits; one issue = one PR; branch `agent/<issue>-<slug>`; PR body `Closes #N`.
- Don't add dependencies without stating why in the PR; update uv.lock.
## Definition of Done
1. Acceptance criteria of the issue met, each with a test (unit or e2e-with-fake).
2. `make check` green locally; CI green.
3. Public behavior change → docs/ page updated; new decision → ADR.
4. docs/llm-wiki: append `## [YYYY-MM-DD] issue #N | <title>` to wiki/log.md; update touched concept/entity pages + index.md. Never edit wiki/raw/.
5. No secrets, no TODOs without a linked issue.
## When blocked
- Ambiguous spec → comment on the issue with options + recommendation, label `needs-decision`, stop.
```

## 7. CI workflows (minimal)

**`.github/workflows/ci.yml`**
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with: { enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src
      - run: uv run pytest -m "not real_anki" --cov=anki_helpers --cov-fail-under=85   # unit + e2e against fake
      - run: uv run python scripts/wiki_lint.py
      - run: uv run zensical build   # or: mkdocs build --strict
```

**`.github/workflows/claude.yml`** (issue-driven agent)
```yaml
name: claude
on:
  issues: { types: [labeled] }
  issue_comment: { types: [created] }
  pull_request_review_comment: { types: [created] }
permissions: { contents: write, pull-requests: write, issues: write, id-token: write }
jobs:
  agent:
    if: >
      (github.event_name == 'issues' && github.event.label.name == 'agent') ||
      (github.event_name != 'issues' && contains(github.event.comment.body, '@claude') &&
       contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association))
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v5
        with: { fetch-depth: 0 }
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --all-extras --dev
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: ${{ github.event_name == 'issues' && format('Implement issue #{0} following CLAUDE.md and its Definition of Done. Open a PR that closes it.', github.event.issue.number) || '' }}
          claude_args: >-
            --max-turns 40
            --allowedTools "Read,Edit,Write,Bash(uv run:*),Bash(make:*),Bash(git:*),Bash(gh pr:*),Bash(gh issue view:*),Bash(gh issue comment:*)"
```

**`.github/workflows/real-anki.yml`** (optional): `workflow_dispatch` + weekly cron. Starts the headless-Anki container (`QT_QPA_PLATFORM=offscreen`, port 8765) as a service and runs `pytest -m real_anki tests/contract`. The exact image/tag is pinned in S1-08.

**Security notes:**
- Issue text is untrusted prompt input. RyotaK (GMO Flatt Security, "Poisoning Claude Code: One GitHub Issue to Break the Supply Chain", 1 Jun 2026) showed that a single crafted issue could get past claude-code-action's write-permission check, because any actor whose name ended in "[bot]" passed. Anthropic fixed this in Claude Code GitHub Actions v1.0.94.
- Only maintainers can apply the `agent` label (label events require triage rights), and comment triggers are restricted by `author_association`.
- Never set `allowed_non_write_users: "*"`.\[28\]
- Keep the tool allowlist narrow.
- Require PR review before merge. Branch protection: `ci/check` required.

## 8. Stages and issues

Issue format: **ID · title** — *AC* (acceptance criteria). All issues get the label `agent` + `stage:Sx`. Each must be completable in one PR (≤ ~400 LOC).

### Stage 0 — Bootstrap (goal: agent-ready repo, green CI)
- **Scope:** tooling migration, conventions, CI, spec/wiki skeletons, legacy commands preserved.
- **Deliverables:** `pyproject.toml` (uv/hatchling), `uv.lock`, `Makefile`, `.pre-commit-config.yaml`, `CLAUDE.md`, `SPEC.md` v0, `ci.yml`, `claude.yml`, `ISSUE_TEMPLATE/agent-task.yml`, `docs/llm-wiki` skeleton, `docs/adr/0001-stack.md`.
- **Acceptance:** `make check` green on CI; `anki-helpers --help` lists legacy commands; claude.yml triggers on a test issue.
- **Tests:** CLI smoke (Typer `CliRunner`), `--version`.
- **Issues:**
  - S0-01 · Inventory current repo — *AC: `docs/llm-wiki/raw/legacy-inventory.md` lists modules, deps, AnkiConnect calls, open PRs with recommendation (merge/close/port).* (human-reviewed)
  - S0-02 · Migrate Poetry→uv + hatchling, src layout `anki_helpers` — *AC: `uv sync --locked` works; entrypoint `anki-helpers`; poetry files removed.*
  - S0-03 · Add ruff, mypy --strict, pre-commit, Makefile `check` — *AC: `make check` passes; pre-commit runs same hooks.*
  - S0-04 · Port unittest→pytest; CLI on Typer preserving `list-deck`, `list-red-flags`, `get-examples-for-red-flags-cards` signatures — *AC: existing behaviors covered by CliRunner tests (Anki calls mocked).*
  - S0-05 · Add ci.yml + claude.yml + issue template + labels (`agent`, `needs-decision`, `stage:*`) — *AC: CI required on PR; a labelled dummy issue yields a PR.*
  - S0-06 · CLAUDE.md + SPEC.md v0 (outline §5) + ADR-0001 — *AC: files present; wiki_lint stub passes.*
  - S0-07 · llm-wiki skeleton + `scripts/wiki_lint.py` — *AC: index/log/SCHEMA exist; lint fails on unindexed page (tested).*

### Stage 1 — AnkiConnect client + fake (goal: everything testable without Anki) — depends S0
- **Deliverables:** `ankiconnect/`, `fake_anki/`, `cli mock serve`, fixtures, contract harness.
- **Acceptance:** all legacy commands run against `mock serve`; the contract suite passes on the fake; optionally on the real container.
- **Tests:** unit (MockTransport), e2e (uvicorn on random port), contract (`real_anki`).
- **Issues:**
  - S1-01 · `AnkiPort` protocol + pydantic request/response models + error types — *AC: v6 envelope; `error!=null` → `AnkiConnectError` with action+message.*
  - S1-02 · `AnkiConnectClient` (httpx) incl. `multi` batching, timeout, retry on connection error only — *AC: tests via MockTransport; never retries on API error.*
  - S1-03 · Fake state + deck/model actions (`version, deckNames, createDeck, modelNames, modelFieldNames`) with stock models Basic/Basic+reversed/Cloze — *AC: shape-identical responses to recorded fixtures.*
  - S1-04 · Fake note actions (`addNote(s), canAddNotes(WithErrorDetail), findNotes` (subset query: `deck:`, `tag:`, `nid:`, `"field:..."`), `notesInfo` incl. `mod`, `notesModTime`, `updateNote(Fields)`, `addTags/removeTags`, `deleteNotes`, `findCards/cardsInfo/suspend`) — *AC: duplicate add errors; `mod` bumps on change via injected clock.*
  - S1-05 · Fake media + `sync` no-op + `multi` — *AC: store/retrieve base64 round-trip; missing → `false`.*
  - S1-06 · Fake HTTP server + `anki-helpers mock serve` + `/_state`, `/_reset`, `/_seed`, fault injection — *AC: e2e fixture starts on random port; legacy CLI works against it.*
  - S1-07 · Port legacy commands onto `AnkiPort` — *AC: `list-red-flags` sorted by due desc, default 5; e2e against fake.*
  - S1-08 · Contract suite + `real-anki.yml` + `record_contract.py` — *AC: same scenarios pass on fake; workflow_dispatch run documented (image pinned).*

### Stage 2 — Markdown data model (goal: lossless, validated vault model) — depends S0; parallel with S1
- **Deliverables:** `notes/` (schema, parse, render, hashing, media, cloze), JSON Schema export, `validate` command, `docs/data-model.md`.
- **Acceptance:** parse→serialize round-trip is byte-stable for canonical files (hypothesis); `anki-helpers vault validate` reports errors with file:line.
- **Issues:**
  - S2-01 · Front-matter pydantic schema (§4.2) + JSON Schema export — *AC: invalid model/missing fields rejected; schema committed & docs generated.*
  - S2-02 · Parser/serializer (ruamel round-trip, H2 field sections) — *AC: comments/key order preserved; property test round-trip.*
  - S2-03 · Deck mapping (dir→`A::B`, override) + field mapping validation vs `modelFieldNames` — *AC: unknown field → error naming the model.*
  - S2-04 · MD→HTML renderer (markdown-it-py; code, tables, MathJax passthrough) + HTML→MD (markdownify) — *AC: golden tests; cloze markers untouched.*
  - S2-05 · Normalized hashing (`md_hash`, `html_hash`) — *AC: whitespace/key-order changes don't alter hash; field edits do.*
  - S2-06 · Media resolver (content-addressed names, Obsidian `ǃ[[x]]` normalization) — *AC: same file → same name; missing file → validation error.*
  - S2-07 · `vault init` / `vault new --model Basic --deck X` scaffolding — *AC: generates a valid file with ULID.*

### Stage 3 — Bidirectional sync (goal: safe, idempotent MD↔Anki) — depends S1, S2
- **Deliverables:** `sync/` (plan, apply, conflicts, state), `anki-helpers sync [--dry-run|--prefer|--prune|--import]`, `resolve`, `docs/sync.md`.
- **Acceptance:** the full state matrix (§4.3) is covered by e2e tests against the fake; a second run yields 0 ops; conflicts never overwrite.
- **Issues:**
  - S3-01 · `plan()` pure diff incl. state matrix — *AC: table-driven test per row.*
  - S3-02 · Push: add (write-back after success), update, deck change, tags — *AC: crash between add and write-back is recoverable via `findNotes` on `uid` tag (test with fault injection).*
  - S3-03 · Pull: Anki-changed → rewrite body, refresh hashes; `--import` managed notes without files — *AC: e2e edits note in fake, sync updates file.*
  - S3-04 · Conflict handling + `.conflict.md` + `--prefer` + `resolve` — *AC: both-changed → exit 3, no writes; each prefer mode tested.*
  - S3-05 · Deletions/orphans: tag+suspend default, `--prune` — *AC: no `deleteNotes` call without `--prune` (asserted on fake log).*
  - S3-06 · Media sync (store on push, retrieve on pull) — *AC: idempotent, no duplicate uploads.*
  - S3-07 · Post-write verification (`updateNoteFields` browser caveat) + `--dry-run` JSON output — *AC: fault-injected silent no-op → warning + nonzero exit.*
  - S3-08 · Idempotency + perf: 1,000-note vault sync ≤ N `multi` calls — *AC: second run 0 write ops; batch size configurable.*

### Stage 4 — Docs site + exploration (goal: published HTML docs) — depends S0 (content from S1–S3)
- **Issues:**
  - S4-01 · `mkdocs.yml` + Zensical build + Pages deploy — *AC: CI builds; site published on main.*
  - S4-02 · `architecture.md` (Mermaid C4 + AnkiPort) — *AC: diagrams render; reflects code modules.*
  - S4-03 · `exploration/ankiconnect-api.md` from recorded fixtures — *AC: every action used by code documented with request/response sample.*
  - S4-04 · `exploration/existing-tools.md` + `obsidian-sync.md` — *AC: tables per §4.2/§4.6.*
  - S4-05 · CLI reference auto-generated (Typer) + data-model page from JSON Schema — *AC: regenerated in CI; diff check.*
  - S4-06 · Include llm-wiki in nav (index, concepts) — *AC: wiki pages build with working links.*

### Stage 5 — MCP server (goal: agent can inspect/debug) — depends S1–S3
- **Issues:**
  - S5-01 · FastMCP server skeleton, stdio, `anki-helpers mcp` + committed `.mcp.json` — *AC: in-memory client lists tools.*
  - S5-02 · Read tools: `list_decks`, `find_notes`, `get_note`, resources `anki://…` — *AC: tests against fake.*
  - S5-03 · Vault tools: `validate_vault`, `diff_note`, `sync_plan` — *AC: diff shows field-level changes.*
  - S5-04 · `sync_apply(confirm)` + mock tools gated by backend — *AC: without `confirm=True` returns plan only; mock tools absent when backend=ankiconnect.*
  - S5-05 · `wiki://index` resource + prompts — *AC: resource returns index.md.*

### Stage 6 — LLM generation (goal: book/topic → reviewed cards, history-safe regen) — depends S2, S3 (S5 optional)
- **Issues:**
  - S6-01 · `CardGenerator` protocol + `FakeProvider` + `AnthropicProvider` (structured output, retries, token/cost log) — *AC: provider selected via config; no network in tests.*
  - S6-02 · Ingest EPUB/PDF/MD → sections with locators — *AC: fixtures (public-domain EPUB/PDF) produce stable section list.*
  - S6-03 · Chunker + `chunk_id` — *AC: unchanged text → same id; edit → new id.*
  - S6-04 · Prompt v1 (SuperMemo rules, cloze guidance) + versioning — *AC: prompt file hashed into `gen.prompt`.*
  - S6-05 · Validator (grounding quote, atomicity heuristics, length, dedupe, over-generate+rank) — *AC: each rule has failing/passing fixtures.*
  - S6-06 · Draft writer + `gen promote` — *AC: drafts excluded from sync until promoted.*
  - S6-07 · Regeneration (`card_key` match → update same `note_id`; unmatched → retired) — *AC: e2e: regen after source edit keeps note_ids; fake review data untouched; no deletes.*
  - S6-08 · Port red-flag example generation onto `CardGenerator` — *AC: legacy command works with FakeProvider; OpenAI optional extra.*
  - S6-09 · Offline eval harness (golden chunks → card metrics) — *AC: report of rule-violation rate per prompt version.*

### Stage 7 — Web UI + vault sync + homelab (goal: browser authoring) — depends S3, S6
- **Issues:**
  - S7-01 · FastAPI+HTMX skeleton, auth hook (trusted header / token), health — *AC: TestClient tests; runs via `anki-helpers web`.*
  - S7-02 · Vault browser + editor + live preview + front-matter form — *AC: save produces schema-valid file.*
  - S7-03 · Git vault backend (clone/pull/commit/push, conflict surfacing) — *AC: e2e with a local bare repo.*
  - S7-04 · Sync page (plan/diff/apply/conflicts) against configured backend — *AC: works against fake.*
  - S7-05 · Generate wizard (upload → chunks → drafts → promote) — *AC: FakeProvider e2e.*
  - S7-06 · `deploy/compose.yaml` (web, optional anki-hub, Caddy) + `docs/web.md` hosting guide with security checklist — *AC: `docker compose config` valid; AnkiConnect not published to host by default.*
  - S7-07 · Desktop sync agent mode (`sync --watch`/cron docs) for baseline topology — *AC: documented + tested loop with fake.*

**Dependency order:** S0 → {S1 ∥ S2} → S3 → {S4 (continuous), S5} → S6 → S7. S4 issues can start after S0 and be refreshed after each stage. S6-01..S6-05 depend only on S2 and can start early.

## 9. Assumptions (explicit)
- A1 Python 3.12, Linux CI only.
- A2 One file = one note; directory = deck.
- A3 Conflict default = no-overwrite + conflict file.
- A4 Deletion default = tag + suspend.
- A5 Claude is the default LLM; OpenAI is optional.
- A6 The vault is a git repo.
- A7 Obsidian Sync has no usable API.
- A8 The template repo's contents are unknown; §2 is the fallback.
- A9 The homelab runs Docker and has Tailscale or SSO in front.

## 10. Open decisions
- D1 mypy vs pyright.
- D2 AnkiConnect v6 only vs adding the new JSON-RPC v1 adapter (verify upstream).
- D3 Conflict policy default (A3) vs LWW.
- D4 Standalone FastMCP vs official `mcp` SDK `MCPServer`.
- D5 Zensical vs pinned Material/MkDocs 1.x.
- D6 Multi-card-per-file support (useful for book chapters) — deferred.
- D7 Homelab hub topology (option 2) vs desktop-only.
- D8 License: keep Unlicense?

## 11. Risks
- **AnkiConnect API drift** (v1 JSON-RPC, Anki 26.08+ requirement). Mitigation: `AnkiPort`, contract tests, weekly real-anki job.
- **Fake/real divergence.** Mitigation: recorded fixtures + contract diff in CI.
- **HTML↔MD lossy round-trip** causes spurious pulls. Mitigation: `html_hash` gating; canonical MD is authoritative for formatting.
- **AnkiWeb full-sync conflicts** with a hub container. Mitigation: hub optional; document "one writer at a time".
- **LLM hallucination/low-quality cards.** Mitigation: grounding-quote check, drafts + review, eval harness.
- **Prompt injection via issues** against claude-code-action. Mitigation: maintainer-only label, author_association gate, narrow tool allowlist, required review.
- **Dependency churn** (FastMCP majors, MkDocs ecosystem collapse). Mitigation: pin majors; ADRs.
- **Secrets exposure** (`ANTHROPIC_API_KEY`, AnkiConnect `apiKey`, git deploy key). Mitigation: env-only, never in vault/front matter; AnkiConnect never published beyond the internal network.

## Sources

1. [GitHub - davojta/anki-helpers: Utils to work with anki app data](https://github.com/davojta/anki-helpers)
2. [GitHub - ankiultimate/anki-connect](https://github.com/ankiultimate/anki-connect)
3. [Update to AnkiConnect 26.10.11.4 by kitschpatrol · Pull Request #8 · kitschpatrol/yanki-connect · GitHub](https://github.com/kitschpatrol/yanki-connect/pull/8)
4. [headless anki](https://github.com/ThisIsntTheWay/headless-anki)
5. [GitHub - ankimcp/headless-anki: Docker images for running Anki headlessly with VNC access and AnkiConnect/MCP server support. · GitHub](https://github.com/ankimcp/headless-anki)
6. [GitHub - glechic/anki-connect-server: Headless AnkiConnect-compatible REST API server with AnkiWeb sync support and MCP server integration. · GitHub](https://github.com/glechic/anki-connect-server)
7. [GitHub - n4tt0u/Obsidian\_to\_Anki\_Kai: Script to add flashcards from text/markdown files to Anki · GitHub](https://github.com/n4tt0u/Obsidian_to_Anki_Kai)
8. [Updating existing notes · ObsidianToAnki/Obsidian\_to\_Anki Wiki · GitHub](https://github.com/Pseudonium/Obsidian_to_Anki/wiki/Updating-existing-notes)
9. [inka2 · PyPI](https://pypi.org/project/inka2/)
10. [Synchronization with Anki · ubiqel/inka Wiki · GitHub](https://github.com/ubiqel/inka/wiki/Synchronization-with-Anki)
11. [GitHub - benwr/ankdown: Easily make Anki flash cards in markdown · GitHub](https://github.com/benwr/ankdown)
12. [FastMCP — MCP Servers · Directories by Enterprise DNA](https://enterprisedna.co/directories/mcp/fastmcp/)
13. [fastmcp · PyPI](https://pypi.org/project/fastmcp/)
14. [FastMCP 4 Tutorial: Build an MCP Server in Python, From First Tool to OAuth](https://www.danilchenko.dev/posts/fastmcp-mcp-server/)
15. [FastMCP vs MCP Python SDK: Key Differences in 2026](https://www.agenticwire.news/article/fastmcp-vs-mcp-python-sdk)
16. [\# ๐ง Anki MCP](https://glama.ai/mcp/servers/@arielbk/anki-mcp/blob/21257cbfc9e972cee109dfdd10e709a07a7158be/README.md)
17. [\# Anki MCP Server](https://glama.ai/mcp/servers/@letuanvu08/anki-mcp/blob/44ddd243b5f941ecfe5f2d436ba123981a909683/README.md)
18. [\# anki-mcp](https://glama.ai/mcp/servers/@hbd/anki-mcp/blob/6e7f12e66c2719571fbe258bfb69dcf8fbd68874/README.md)
19. [Anki MCP Server](https://mcpservers.org/servers/dhkim0124/anki-mcp-server)
20. [AnkiGPT: teach ChatGPT to create cards for you - Add-ons - Anki Forums](https://forums.ankiweb.net/t/ankigpt-teach-chatgpt-to-create-cards-for-you/27480)
21. [How to Convert Notes to Flashcards with AI](https://studycardsai.com/blog/convert-notes-to-flashcards-ai)
22. [Obsidian MCP Setup 2026: Local REST API Complete Guide — MCP.Directory](https://mcp.directory/blog/obsidian-mcp-complete-guide-2026)
23. [obsidian-local-rest-api: REST API and MCP for Obsidian](https://hysenlabs.com/en/projects/coddingtonbear-obsidian-local-rest-api)
24. [서버에서 Anki 실행하기: Docker + AnkiConnect API 구축 - DEV Community](https://dev.to/dss99911/seobeoeseo-anki-silhaenghagi-docker-ankiconnect-api-gucug-2f90)
25. [Releases · squidfunk/mkdocs-material · GitHub](https://github.com/squidfunk/mkdocs-material/releases)
26. [Changelog - Material for MkDocs](https://squidfunk.github.io/mkdocs-material/changelog/)
27. [llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
28. [Poisoning Claude Code: One GitHub Issue to Break the Supply Chain - GMO Flatt Security Research](https://flatt.tech/research/posts/poisoning-claude-code-one-github-issue-to-break-the-supply-chain/)
