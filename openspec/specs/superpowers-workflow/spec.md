## ADDED Requirements

### Requirement: Superpowers plugin is installed and active
The system SHALL have the Superpowers plugin installed via the Claude Code official plugin marketplace.

#### Scenario: Plugin installation succeeds
- **WHEN** the user runs the plugin install command
- **THEN** the Superpowers plugin is registered and available in the Claude Code session

#### Scenario: Session start loads superpowers context
- **WHEN** a new Claude Code session starts
- **THEN** the SessionStart hook injects the `using-superpowers` skill content into the session context

### Requirement: Superpowers skills are discoverable and invocable
The agent SHALL be able to invoke any Superpowers skill using the Skill tool during a session.

#### Scenario: Brainstorming skill triggers on feature request
- **WHEN** the user asks to build a new feature
- **THEN** the agent invokes the `superpowers:brainstorming` skill before responding

#### Scenario: TDD skill triggers during implementation
- **WHEN** the agent is about to write implementation code
- **THEN** the agent invokes the `superpowers:test-driven-development` skill

### Requirement: Superpowers and OpenSpec coexist
The system SHALL allow both Superpowers and OpenSpec skills to operate without conflicts.

#### Scenario: Both skill sets are available
- **WHEN** a session starts with Superpowers installed
- **THEN** both OpenSpec skills (`openspec-propose`, `openspec-apply`, etc.) and Superpowers skills (`brainstorming`, `writing-plans`, etc.) are accessible

#### Scenario: User can use OpenSpec workflow independently
- **WHEN** the user invokes `/opsx:propose` or `/opsx:apply`
- **THEN** the OpenSpec workflow executes normally without Superpowers interference

### Requirement: CLAUDE.md documents Superpowers installation
The project's CLAUDE.md SHALL contain a reference to Superpowers being installed and active.

#### Scenario: CLAUDE.md mentions Superpowers
- **WHEN** the CLAUDE.md file is read
- **THEN** it contains a note that Superpowers is installed and skills are auto-loaded at session start
