# Confidence Law

**Domain:** Confidence
**Constitutional Basis:** Article XIII

---

## Purpose

Govern how confidence is computed, maintained, and expressed for every knowledge object in the system.

## Responsibilities

- Compute confidence from evidence chains
- Adjust confidence on contradiction detection
- Surface confidence levels in context rendering
- Ensure low-confidence knowledge is expressed as uncertain
- Allow high-confidence knowledge to be expressed decisively

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Increase | Yes | When corroborating evidence is added |
| Decrease | Yes | When contradictory evidence is added |
| Set explicitly | Yes | Only for initial creation (first evidence) |

## Conflict Resolution

- Confidence is computed from the evidence chain, never set arbitrarily
- Multiple unique values for the same field decrease confidence: `max(0.1, 0.7 - 0.15 × (unique_values - 1))`
- Reinforcement increases confidence: `min(1.0, 0.65 + 0.05 × n)`

## Confidence Levels

| Range | Label | Expression |
|-------|-------|------------|
| 0.85 - 1.0 | High confidence | Decisive, certain |
| 0.65 - 0.85 | Moderate confidence | Confident but open |
| 0.50 - 0.65 | Low confidence | Express uncertainty |
| 0.00 - 0.50 | Very low confidence | Admit not knowing |

## Evidence Requirements

- Every confidence score must be computable from the entity's evidence chain
- Confidence must be recalculated when evidence is added
- The computation formula must be deterministic

## Lifecycle

1. **Initial** — Confidence set from first evidence
2. **Reinforcement** — Same-value evidence increases confidence
3. **Contradiction** — Different-value evidence decreases confidence
4. **Stabilization** — Repeated reinforcement without contradiction stabilizes confidence
5. **Reset** — Only possible through evidence chain clearing

## Examples

```python
# Agreement builds confidence
profile.add_or_update("color", "blue")  # conf=0.70
profile.add_or_update("color", "blue")  # conf=0.75
profile.add_or_update("color", "blue")  # conf=0.80

# Contradiction drops confidence
profile.add_or_update("color", "red")   # conf=0.55, contradictions=1
profile.add_or_update("color", "green") # conf=0.40, contradictions=2
```

## Future Extensions

- Confidence quality score (how reliable is the evidence source?)
- Confidence decay over time
- Minimum confidence thresholds for action
- Confidence-based retrieval filtering
