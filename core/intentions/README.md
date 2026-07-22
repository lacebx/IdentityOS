# Intention Engine

**Path:** `core/intentions/`

## Overview

Manages short-term commitments formed during conversation. Intentions are NOT goals — they are steps toward goals or standalone promises that auto-expire.

## Key Classes

- **`Intention`** — A commitment with description, status, priority, expiry, source conversation
- **`IntentionEngine`** — Manages intentions, handles auto-expiry, completion, abandonment, promotion to goals
- **`IntentionStatus`** — `ACTIVE`, `COMPLETED`, `ABANDONED`, `EXPIRED`, `PROMOTED`
- **`IntentionPriority`** — `LOW`, `MEDIUM`, `HIGH`
- **`PromotionReason`** — `REPEATED`, `SUSTAINED_RELEVANCE`, `USER_REQUEST`, `SYSTEM_PROMOTION`

## Lifecycle

```
ACTIVE → COMPLETED   (explicit completion)
       → ABANDONED   (explicit abandonment)
       → EXPIRED     (automatic — time passed)
       → PROMOTED    (promoted to a Goal)
```

## Auto-Expiry

Intentions have a default expiry of 24 hours. The `check_expiry()` method auto-expires any active intentions past their deadline. Call this periodically (e.g., at the start of each interaction).

## Promotion to Goals

Sustained intentions can be promoted to `Goal` objects. The engine records the promotion reason and links the intention to the goal.

## Serialization

Both `Intention` and `IntentionEngine` support `to_dict()` / `from_dict()`.

## Confidence

Intention exposes a `confidence` property (0.0–1.0) based on priority, time remaining, and status, with a `confidence_label` string.
