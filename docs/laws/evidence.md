# Evidence Law

**Domain:** Evidence
**Constitutional Basis:** Article IV

---

## Purpose

Govern how evidence is created, linked, and traced for every knowledge object in the system. Evidence is the foundation of truth in IdentityOS.

## Responsibilities

- Record evidence for every fact, preference, belief, relationship, goal, and intention
- Provide evidence chain traceability
- Support evidence-based confidence computation
- Store evidence immutably
- Link evidence to source conversations and memories

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create | Yes | Always, when a claim is made |
| Read | Yes | Always |
| Supersede | Yes | By newer evidence |
| Delete | No | Evidence is immutable |

## Conflict Resolution

- Evidence may not be deleted, only superseded
- Multiple evidence records for the same field create an evidence chain
- Conflicting evidence reduces confidence; it does not delete prior evidence
- The evidence graph records the full provenance of every claim

## Evidence Requirements

Every evidence record must contain:
- **source** — Where the evidence came from (conversation, API, import)
- **timestamp** — When the evidence was recorded
- **confidence** — The confidence at the time of recording
- **reason** — Why this evidence supports the claim
- **conversation** — The conversation text (if applicable)
- **memory_id** — The memory fragment id (if linked)
- **support_strength** — How strongly this evidence supports the claim

## Lifecycle

1. **Creation** — Evidence record created when a claim is made
2. **Storage** — Added to the entity's evidence chain
3. **Reinforcement** — Corroborating evidence increases confidence
4. **Contradiction** — Conflicting evidence creates tension in the chain
5. **Supersession** — New evidence may supersede old evidence

## Examples

```python
evidence = EvidenceRecord(
    value="blue",
    source_turn="User: My favorite color is blue",
    timestamp="2026-07-22T01:00:00",
    turn_index=42,
)
# Added to preference's evidence chain
```

## Future Extensions

- Evidence graph visualization
- Cross-entity evidence linking
- Evidence quality scoring
- Automated evidence contradiction detection
