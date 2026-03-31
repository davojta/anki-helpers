## Why

The project currently lacks a structured development workflow for AI-assisted coding. Adding Superpowers (obra/superpowers) brings a battle-tested skill system — brainstorming, TDD, systematic debugging, code review, and subagent-driven development — that enforces discipline and consistency across coding sessions.

## What Changes

- Install the Superpowers plugin via the official Claude Code plugin marketplace
- Configure the SessionStart hook so skills load automatically on session start
- Integrate Superpowers skills alongside the existing OpenSpec skills (both coexist in `.claude/skills/`)
- Update CLAUDE.md to reference Superpowers workflows where relevant

## Capabilities

### New Capabilities
- `superpowers-workflow`: Enables the full Superpowers skill system — brainstorming, writing-plans, subagent-driven-development, TDD, systematic-debugging, code-review, and git-worktree workflows — triggered automatically via the SessionStart hook

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- `.claude/` directory: new skills and hook configuration
- `CLAUDE.md`: minor additions referencing Superpowers workflows
- Developer workflow: session start will inject Superpowers context automatically
- Coexists with existing OpenSpec skills — no conflicts expected
