# Intentions Law

**Domain:** Intentions
**Constitutional Basis:** Article IX

---

## Purpose

Govern how identities form and manage short-term commitments. Intentions are NOT goals — they are steps toward goals or standalone promises.

## Responsibilities

- Capture commitments made during conversation
- Track intention lifecycle (active → completed/expired)
- Enforce automatic expiry
- Promote sustained intentions to goals
- Influence responses based on active intentions

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create | Yes | Through conversation or API |
| Complete | Yes | When the commitment is fulfilled |
| Abandon | Yes | When the commitment is no longer relevant |
| Promote | Yes | When intention demonstrates sustained relevance |
| Expire | Automatic | After expiry timestamp passes |

## Conflict Resolution

- Active intentions take priority over goals in short-term response planning
- When an intention contradicts a goal, the goal's priority decides
- Expired intentions are archived, not deleted

## Evidence Requirements

- Every intention must have an expiry timestamp
- Completion should be attributed to a conversation turn
- Promotion to goal must record the reason

## Lifecycle

```
Created (active) → Completed
                 → Abandoned
                 → Expired (automatic)
                 → Promoted (becomes a Goal)
```

## Examples

```python
intention = Intention(
    description="Ask user about their weekend plans",
    expires_at=datetime.now() + timedelta(hours=1),
)
intention_engine.add(intention)

# Later:
intention.complete()
# Or automatically after 1 hour:
# → status = expired
```

## Future Extensions

- Intention extraction from conversation ("I'll do X")
- Automatic expiry webhook
- Cross-session intention tracking
- Intention chains (one intention triggers another)
