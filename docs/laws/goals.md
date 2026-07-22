# Goals Law

**Domain:** Goals
**Constitutional Basis:** Article VIII

---

## Purpose

Govern how identities form, pursue, and complete long-term objectives. Goals are distinct from intentions (short-term commitments).

## Responsibilities

- Create, track, and manage goals
- Determine goal priority and dependencies
- Influence identity behavior based on active goals
- Report goal progress and blockers
- Persist goals across sessions

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create | Yes | Through API or mutation engine |
| Activate | Yes | When goal is ready to pursue |
| Update progress | Yes | Through interaction analysis |
| Block | Yes | When dependency is unmet |
| Pause | Yes | On user request or priority change |
| Complete | Yes | When success criteria are met |
| Abandon | Yes | When goal is no longer relevant |

## Conflict Resolution

- Goals with higher priority take precedence in response generation
- Goals may be blocked by unmet dependencies — blocked goals do not influence behavior
- Competing goals should be resolved by priority and progress

## Evidence Requirements

- Every goal records its creation timestamp
- Progress updates should be attributed to specific interactions
- Blocking reasons must be recorded with a timestamp

## Lifecycle

```
Created → Active → Blocked → Active → Completed
                  → Paused → Active
         → Abandoned
```

## Examples

```python
goal = Goal(
    title="Learn user's favorite color",
    description="Discover what color the user prefers through conversation",
    priority=GoalPriority.HIGH,
    success_criteria="favorite_color stored in FactStore with confidence > 0.8",
)
goal_engine.add(goal)

# Goal influences response:
# "I'd like to learn more about your preferences. What's your favorite color?"
```

## Future Extensions

- Goal decomposition into subgoals
- Automatic goal discovery from conversation
- Goal-based memory importance weighting
- Multi-identity goal coordination
