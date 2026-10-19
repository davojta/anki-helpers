# <name>: Tasks

Design: [design.md](design.md) · Validation: [validation.md](validation.md)

Format: `- [ ] T<NNN> [<agent>] [P?] <what>`: `<files>`
- Agent: `[low-dev]` haiku, `[mid-dev]` sonnet, `[high-dev]` opus. Effort: medium for all.
- `[P]`: can run in parallel (different files, no dependency).
- `HITL-n`: stop, ask the human, continue only after the check passes.

## Phase 1: Setup

- [ ] T001 [low-dev] <deps / config / scaffolding>: `<files>`

## Phase 2: Core

- [ ] T002 [high-dev] <types and interfaces from design.md>: `<files>`
- [ ] T003 [mid-dev] [P] <component A>: `<files>`
- [ ] T004 [mid-dev] [P] <component B>: `<files>`
- [ ] **HITL-1**: <check from design.md>

## Phase 3: Integration

- [ ] T005 [mid-dev] <wire components, CLI, errors>: `<files>`

## Phase 4: Tests and polish

- [ ] T006 [mid-dev] [P] Tests T1–T3 from design.md: `tests/...`
- [ ] T007 [low-dev] Run `poetry run pytest` and `poetry run pre-commit run --all-files`, report failures
- [ ] T008 [low-dev] [P] Update docs: `<files>`

## Dependencies

- T002 blocks T003, T004
- T003, T004 block T005
- Core before tests and polish

## Task detail

<!-- Only for tasks that need more than one line. -->

### T002 <name>

- Goal: <one line>
- Do: <steps>
- Done when: <test / check>
