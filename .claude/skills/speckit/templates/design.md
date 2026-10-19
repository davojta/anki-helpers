# Design: <name>

Tier: <smol | medium | big> · Date: <YYYY-MM-DD> · Proposal: [proposal.md](proposal.md) <!-- medium/big only -->

## Data flow

<!-- 3–7 parts. Input on the left, output on the right. Name real components. -->

```
<input> → [<Component A>] → [<Component B>] → [<Component C>] → <output>
```

| # | Component | In | Transform | Out |
|---|-----------|----|-----------|-----|
| 1 | `<module.func>` | `<Type>` | <what it does, one line> | `<Type>` |
| 2 | | | | |

## Types: data flow

<!-- Main types that move through the flow above. Real names, or "new". -->

```python
class <Name>(BaseModel):  # <file> ✅ | new
    <field>: <type>  # <meaning>
```

## Types: critical path

<!-- Types and signatures this change touches. Show before → after. -->

| Symbol | File | Before | After |
|--------|------|--------|-------|
| `<func/class>` | `<path>` | `<old signature>` | `<new signature>` |

## Test scenarios

**T1 positive: <name>**
- Given: <state / input>
- Action: <call / command>
- Result: <exact expected output or state>

**T2 negative: <name>**
- Given: <invalid or edge input>
- Action: <call / command>
- Result: <rejected how, nothing changed>

**T3 error handling: <name>**
- Given: <dependency fails: network, Anki down, bad file>
- Action: <call / command>
- Result: <error type / message / exit code, no partial writes>

## HITL

<!-- smol: delete this section. medium: 1–2. big: 3–5. Also put each marker inline at its decision. -->

> **[HITL-1]** Check: <what>. Why: <risk>. How: <file / command / page>.

## File map

| File | Change | Why |
|------|--------|-----|
| `<path>` | new / mod / del | <one line> |

## Stages

<!-- smol: 1–5. Each stage leaves tests green. -->

1. <stage>: <files>. Done when: <test or check>.
