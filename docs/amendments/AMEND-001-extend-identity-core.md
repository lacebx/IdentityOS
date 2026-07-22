# Amendment 001: Extend Identity Immutable Core

**Amendment ID:** `AMEND-001`
**Status:** `RATIFIED`
**Date:** `2026-07-22`
**Constitutional Articles Affected:** `Article I`
**Laws Affected:** `identity.md`
**Sponsor:** `Architecture Council`

---

## Summary

Extend the identity's immutable core to include a `species` field and a `origin_story` field. These fields are LOCKED at creation and cannot be mutated.

## Motivation

The current immutable core (name, id, class, values) does not capture the identity's origin or nature. Adding `species` allows the identity to express what kind of entity it is (AI, human, synthetic, etc.), and `origin_story` provides a canonical creation narrative that grounds the identity's self-understanding.

## Changes

### Constitutional Changes

- **Article I, Section 2:** Add `species` and `origin_story` to the list of immutable identity properties.

### Law Changes

- **`docs/laws/identity.md`:** Add `species` and `origin_story` to the LOCKED fields table. Add them to the "Allowed Mutations" table with mutability LOCKED. Add them to the Lifecycle Creation step.

## Impact

- **Backward Compatible:** `YES`
- **Migration Required:** `YES` — All existing identities need `species` and `origin_story` values assigned on next load.
- **Breaking Changes:** None. Existing identities will default `species` to `"AI"` and `origin_story` to `"Created with IdentityOS"`.

## Migration Plan

1. Update `IdentitySpec.__init__` to accept `species` and `origin_story` parameters
2. Update serialization/deserialization to include new fields
3. Add migration handler to set defaults for existing persisted identities
4. Update tests to verify immutability of new fields

## Ratification

- **Proposed:** `2026-07-22`
- **Ratified:** `2026-07-22`
- **Ratified By:** `Architecture Council`

## Supersession

- **Superseded By:** N/A
- **Superseded On:** N/A

---

*This amendment is governed by Article XIV of the IdentityOS Constitution.*
