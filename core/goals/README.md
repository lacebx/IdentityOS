# Goal Engine

**Path:** `core/goals.py`

## Overview

Manages long-term objectives for an identity. Goals drive behavior, influence memory retrieval, and shape responses. Goals are distinct from intentions (short-term commitments).

## Key Classes

- **`Goal`** — A goal with title, description, priority, scope, milestones, status lifecycle
- **`GoalEngine`** — Manages the goal stack, supports CRUD, filtering, priority ordering, dependency resolution
- **`GoalStatus`** — `ACTIVE`, `COMPLETED`, `PAUSED`, `ABANDONED`, `BLOCKED`
- **`GoalPriority`** — `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- **`GoalScope`** — `IMMEDIATE`, `SESSION`, `PERSISTENT`, `LIFELONG`

## Lifecycle Transitions

```
ACTIVE → COMPLETED, PAUSED, ABANDONED, BLOCKED
PAUSED → ACTIVE, ABANDONED
BLOCKED → ACTIVE, ABANDONED
COMPLETED → (none)
ABANDONED → (none)
```

Invalid transitions raise `ValueError`.

## Dependency Resolution

Goals can be blocked by other goals via `blocked_by`. The `resolve_blocked()` method checks if any BLOCKED goals have had their dependencies resolved (blocker no longer ACTIVE).

## Serialization

Both `Goal` and `GoalEngine` support `to_dict()` / `from_dict()` for persistence.

## Confidence

Goal exposes a `confidence` property (0.0–1.0) based on progress, priority, and status, with a `confidence_label` string.
