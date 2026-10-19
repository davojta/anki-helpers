---
name: speckit
description: Size a change (simple / smol / medium / big) and write the matching spec docs - plan mode, design.md, input→proposal→design, or research→proposal→design→tasks→validation. Use when the user asks to spec, plan, design, or scope a feature or change before coding, or invokes /speckit. Based on easy-spec (github.com/davojta/easy-spec).
argument-hint: "<what to change> [tier: simple|smol|medium|big] [slug: name]"
---

# speckit

Turn a change request into the smallest spec that fits its size and risk.

## Style (all docs)

- Very laconic. Simple technical English. No filler, no marketing words.
- Bullets and tables over prose. One idea per line.
- Real file paths and real type names from this repo. Read code before writing.
- Mark facts: ✅ verified in code, ⚠️ assumption, ❌ unknown.

## 1. Pick the tier

Read the code the change touches. Estimate files and modules. Pick the tier by the
**highest** matching column. State the tier and the one-line reason before writing
anything. The user can override with `tier:`.

| Tier | Files | Modules | Risk | Output |
|------|-------|---------|------|--------|
| simple | 1–5 | 1 | none / minimal | plan mode, no docs |
| smol | 6–15 | 1–3 | slight, contained | `design.md` |
| medium | 15–30 | 3–7 | medium | `input.md` → `proposal.md` → `design.md` |
| big | 30+ | 7+ | high | `input.md` → `research.md` → `proposal.md` → `design.md` → `tasks.md` + `validation.md` |

Module = a top-level package or folder under `src/anki_helpers/`, plus `tests/`,
`docs/`, CI, or packaging config.

## 2. Where docs go

`docs/tasks/<YYYY-MM-DD>-<slug>/`. Use today's date. Slug is short kebab-case.

If `docs/tasks/ledger.toml` exists, also write `task.md` (template: `templates/task.md`).
Set `parent:` when the change belongs to an umbrella task.

## 3. Tier workflows

### simple

Call `EnterPlanMode`. The plan has: goal (1 line), files to change, the steps, and
one test to add or run. No docs on disk.

### smol

1. Write `design.md` from `templates/design.md`.
2. Skip the `HITL` section.
3. `Stages`: 1–5.

### medium

Write the docs in this order. Each one reads the previous one.

1. `input.md`: the user's input, free form, copied as given. No template, no rewording.
2. `proposal.md` (`templates/proposal.md`): summary (1–3 sentences), why (1–3 sentences),
   high-level overview of what changes.
3. `design.md` (`templates/design.md`) with **1–2 HITL markers**.

Stop after `proposal.md` and ask the user to confirm the direction before writing `design.md`.

### big

1. `input.md`: as for medium.
2. `research.md` (`templates/research.md`): existing patterns in the code, verified facts
   vs assumptions vs gaps, decision matrix. Use subagents for broad code search if needed.
3. `proposal.md`, as for medium. Stop and ask the user to confirm.
4. `design.md` with **3–5 HITL markers**.
5. `tasks.md` (`templates/tasks.md`): each task has a delegation marker (below).
6. `validation.md` (`templates/validation.md`): one block per HITL marker, with exact
   CLI commands to run or the URL to open, and the expected result.

## 4. Markers

**HITL** (human in the loop). A point where a human must check before work continues.
Put it inline at the decision it guards and list every marker in the `HITL` section:

```markdown
> **[HITL-1]** Check: <what to confirm>. Why: <risk if wrong>. How: <file / command / page>.
```

Good HITL spots: data loss or destructive ops, public API or schema changes, security
and secrets, choices between options with real trade-offs, outputs that need human taste
(e.g. LLM card quality).

**Delegation** (big tier, `tasks.md` only). One marker per task:

| Marker | Agent | Effort | Use for |
|--------|-------|--------|---------|
| `[low-dev]` | `low-dev` (haiku) | medium | 1–3 files, mechanical edits, running checks |
| `[mid-dev]` | `mid-dev` (sonnet) | medium | 4–10 files, features, refactors, unit tests |
| `[high-dev]` | `high-dev` (opus) | medium | cross-module design, hard refactors, tricky bugs |

When the tasks run later, spawn the marked agent with `effort: "medium"`.
Mark `[P]` when a task can run in parallel (different files, no dependency).

## 5. Finish

- Re-read every doc once. Cut any line that does not help someone implement or review.
- Check that file paths and type names exist (or are marked as new).
- Report: the tier, the doc paths, the HITL list, and any open questions. Do not start
  implementing unless the user asks.
