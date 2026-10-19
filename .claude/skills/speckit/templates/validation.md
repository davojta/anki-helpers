# <name>: Validation

Design: [design.md](design.md) · Tasks: [tasks.md](tasks.md)

For the human. Run each step and tick it. If a result does not match, stop and report.

## Setup

```bash
poetry install
```

## HITL-1: <what to check>

When: after <task id>.

```bash
<exact command>
```

Expected: <exact output / exit code / file content>.
- [ ] Pass

## HITL-2: <what to check>

Open: <URL or file path>

Expected: <what you should see>.
- [ ] Pass

## Final

```bash
poetry run pytest
poetry run pre-commit run --all-files
```

Expected: all green.
- [ ] Pass
