---
name: task
description: Create a task-ledger task in docs/tasks/ from free-form input and save that input as input.md. Use when the user invokes /task or asks to create, file, or log a new task.
argument-hint: "<free-form task description>"
---

# task

Create a ledger task from the user's free-form input. Example:

```
/task refactor to use uv instead of poetry using the grand plan
```

## 1. Derive fields

- `slug`: short kebab-case, 1–4 words (`uv-migration`). No date; the ledger adds it.
- `title`: short imperative line (`Migrate from Poetry to uv`).
- `parent`: if the input names an existing task (e.g. "grand plan"), find it with
  `ls docs/tasks/` and use its id (`2026-10-19-grand-plan`). Skip if none matches.
- Read the parent's docs only to pick a fitting slug and title. Do not copy them into the task.

Ledger root is `docs/tasks/` (flat layout, `ledger.toml` has `project = "anki-helpers"`).
Task id = `<YYYY-MM-DD>-<slug>`, folder = `docs/tasks/<id>/`. If the folder exists, stop and ask.

## 2. Create the task

**If `ledger` is on PATH** (`command -v ledger`):

```bash
LEDGER_ROOT=$PWD/docs/tasks ledger new <slug> --title "<title>" --json
```

Use the returned path. It creates `task.md`, `input.md`, empty `proposal.md` and `design.md`.

**Otherwise** write the same files by hand. Use today's date for `<date>`:

`task.md`:
```markdown
---
schema: 1
id: <date>-<slug>
title: <title>
project: anki-helpers
status: backlog
created: <date>
updated: <date>
status_changed: <date>
tags: [task]
history:
  - {at: <date>, to: backlog}
---

<one line: what and why>
```

Plus empty `proposal.md` and `design.md`.

## 3. Fill in

- `task.md`: add `parent: <id>` after `tags` if a parent was found. Replace the body with one
  line: what and why.
- `input.md`: keep the user's text exactly as given, no rewording:

```markdown
# <title>

## Input

<user's input, verbatim>
```

## 4. Check and report

- If `ledger` is on PATH: run `LEDGER_ROOT=$PWD/docs/tasks ledger check`, and fix any errors it reports.
- Report: the task id, the folder path, and the parent. Suggest `/speckit` as the next step.
- Do not commit, and do not start the work.
