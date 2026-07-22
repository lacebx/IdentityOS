# Amendment 003: Session-Mode Inheritance

**Amendment ID:** `AMEND-003`
**Status:** `DRAFT`
**Date:** `2026-07-22`
**Constitutional Articles Affected:** `Article XI`
**Laws Affected:** `sessions.md`
**Sponsor:** `Architecture Council`

---

## Summary

Introduce session-mode inheritance, where a session may declare a parent session and inherit its mode. This enables nested simulations and roleplays that preserve their parent's mode isolation.

## Motivation

Currently, each session independently detects its mode from user input. There is no way to create a sub-session that inherits its parent's mode. For example, a dream within a simulation should be detected as DREAM but inherit the simulation's isolation context. This amendment enables nested session mode inheritance.

## Changes

### Constitutional Changes

- **Article XI, Section 3:** Add clause for session-mode inheritance. A session may declare a parent_session_id. If no mode trigger is detected, the session inherits the parent's mode.

### Law Changes

- **`docs/laws/sessions.md`:** Add `parent_session_id` field to session records. Add inheritance rule: if no mode trigger is detected, fall back to parent's mode. Add "Inherited" as a mode detection result.

## Impact

- **Backward Compatible:** `YES`
- **Migration Required:** `NO`
- **Breaking Changes:** None. Inheritance is additive and opt-in.

## Migration Plan

N/A — Feature is additive.

## Ratification

- **Proposed:** `2026-07-22`
- **Ratified:** `TBD`
- **Ratified By:** `TBD`

## Supersession

- **Superseded By:** N/A
- **Superseded On:** N/A

---

*This amendment is governed by Article XIV of the IdentityOS Constitution.*
