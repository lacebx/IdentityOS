# ADR-003: Session-Isolated FactStore Forking

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** Article XI (Sessions)

---

## Context

The system must handle non-NORMAL sessions (roleplay, dream, simulation, hypothetical) where user input contradicts the canonical identity state. The identity must participate in these sessions without canonical contamination.

## Decision

Use FactStore forking: when a non-NORMAL session is detected, the canonical FactStore is shallow-copied. All mutations during the session go to the forked copy. The canonical FactStore remains untouched.

## Rationale

1. **Constitutional compliance** — Article XI requires session isolation. Forking provides clear, auditable isolation.
2. **Session restoration** — The forked FactStore is persisted with the session state, enabling restoration on session resume.
3. **No special-case logic** — The identity code path is identical; only the FactStore reference changes.
4. **Performance** — Shallow copy is O(1); mutations incur copy-on-write overhead only for affected entries.

## Consequences

- Positive: Constitutional compliance with no special-case response logic
- Positive: Session restoration is trivial (reload the fork)
- Negative: Shallow copy shares references to immutable data; deep copy of mutable objects requires care
- Negative: Session merges back to canonical require explicit API

## Compliance

- `core/user_profile.py` — `UserProfile.fork()` method
- Session creation logic in interaction pipeline
