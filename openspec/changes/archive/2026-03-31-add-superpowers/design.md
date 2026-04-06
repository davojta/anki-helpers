## Context

The anki-helpers project uses Claude Code with OpenSpec skills already installed in `.claude/skills/`. The Superpowers framework (github.com/obra/superpowers) provides a complementary set of development workflow skills — brainstorming, TDD, code review, subagent-driven development — that are loaded via a SessionStart hook.

Superpowers is distributed as a Claude Code plugin. When installed, it registers a SessionStart hook that injects the `using-superpowers` skill content into every session, which in turn causes the agent to check for and invoke relevant skills automatically.

## Goals / Non-Goals

**Goals:**
- Install Superpowers via the official Claude Code plugin system
- Ensure Superpowers and OpenSpec skills coexist without conflicts
- Maintain existing project workflows (just commands, OpenSpec commands)

**Non-Goals:**
- Replacing OpenSpec with Superpowers — both systems serve different purposes
- Customizing or overriding individual Superpowers skills
- Changing the existing project testing/linting setup

## Decisions

### 1. Installation method: Claude Code plugin marketplace

**Decision**: Install via `/plugin install superpowers@claude-plugins-official` (official marketplace).

**Alternatives considered**:
- Manual file copy from the local clone at `/home/dzianis/projects/dev/github/superpowers` — fragile, no auto-updates
- `obra/superpowers-marketplace` third-party marketplace — functional but official is preferred now that it exists

**Rationale**: The official marketplace provides automatic updates and is the recommended installation path. The local clone is useful for reference but shouldn't be the installation source.

### 2. Skill coexistence strategy

**Decision**: Keep both OpenSpec and Superpowers skills in `.claude/skills/`. No changes to existing skill files.

**Rationale**: Superpowers skills are loaded via the plugin system and injected at session start. OpenSpec skills are loaded via the Skill tool on demand. They operate independently — Superpowers handles development workflow (brainstorming, TDD, debugging), OpenSpec handles change management (propose, apply, archive). No namespace collisions.

### 3. CLAUDE.md updates

**Decision**: Add a brief note in CLAUDE.md that Superpowers is installed, so the agent knows to check for skills. No major restructuring.

**Rationale**: The SessionStart hook already injects the `using-superpowers` skill content, so CLAUDE.md doesn't need to duplicate instructions. A single line reference is sufficient for discoverability.

## Risks / Trade-offs

- **Skill invocation overhead** → Superpowers encourages checking skills before every response. For simple tasks this adds a small overhead, but user instructions in CLAUDE.md take priority and can override.
- **Plugin updates may change behavior** → Mitigated by using official marketplace (stable channel). Can pin version if needed.
- **Conflicting guidance between Superpowers and OpenSpec** → Unlikely: Superpowers focuses on development workflow, OpenSpec on change lifecycle. If a conflict arises, user CLAUDE.md instructions take priority per Superpowers' own priority rules.
