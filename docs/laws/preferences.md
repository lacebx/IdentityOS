# Preferences Law

**Domain:** Preferences
**Constitutional Basis:** Article VI

---

## Purpose

Govern how preferences are discovered, stored, evolved, and expressed. Preferences are EVOLVABLE — they change with evidence.

## Responsibilities

- Extract preference statements from user conversation
- Store preferences in the FactStore with full evidence chains
- Track confidence as evidence accumulates
- Detect and flag contradictory preferences
- Render preferences in context for the LLM

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create | Yes | Through extraction pattern match |
| Reinforce | Yes | Same value repeated increases confidence |
| Change | Yes | New value with contradictory evidence |
| Flag uncertain | Yes | Automatic on contradiction detection |
| Delete | Yes | Through FactStore API |

## Conflict Resolution

- When a user states a preference that contradicts a stored preference, both values enter the evidence chain
- Confidence is computed from the evidence chain using Bayesian-ish formula: `0.65 + (0.05 × n)` for agreement, `0.7 - (0.15 × (unique_values - 1))` for contradiction
- Contradictory preferences are rendered as "(uncertain — contradictory reports)"
- The identity should express uncertainty when asked about a contradictory preference

## Evidence Requirements

- Every preference change must record the source conversation
- Evidence records must include: value, source_turn, timestamp, turn_index
- Contradictions must increment the contradictions counter

## Lifecycle

1. **Discovery** — User states "my favorite X is Y"
2. **Extraction** — Pattern match captures field + value
3. **Storage** — Stored in UserProfile with evidence record
4. **Reinforcement** — Same value repeated increases confidence
5. **Contradiction** — Different value creates contradiction flag
6. **Uncertainty** — Multiple contradictions trigger uncertain status

## Examples

```python
profile.add_or_update("favorite_color", "blue", source="first")
# → confidence=0.70, uncertain=False

profile.add_or_update("favorite_color", "blue", source="second")
# → confidence=0.75, uncertain=False

profile.add_or_update("favorite_color", "red", source="third")
# → confidence=0.55, uncertain=True, contradictions=1
```

## Future Extensions

- Preference-derived recommendations
- Preference clusters (color preferences, food preferences, etc.)
- Cross-identity preference comparison
