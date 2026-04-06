## 1. Install Superpowers Plugin

- [x] 1.1 Run `/plugin install superpowers@claude-plugins-official` to install from the official marketplace
- [x] 1.2 Start a new session and verify the SessionStart hook fires (agent should mention superpowers context)

## 2. Verify Skill Integration

- [x] 2.1 Test that Superpowers skills are invocable (e.g., ask agent to brainstorm a simple idea and confirm it invokes `superpowers:brainstorming`)
- [x] 2.2 Test that OpenSpec skills still work (run `/opsx:explore` and confirm it loads normally)
- [x] 2.3 Confirm no errors or conflicts in the session output

## 3. Update Documentation

- [x] 3.1 Add a brief note to CLAUDE.md that Superpowers is installed and skills auto-load at session start
- [x] 3.2 Verify the updated CLAUDE.md renders correctly and doesn't conflict with existing sections
