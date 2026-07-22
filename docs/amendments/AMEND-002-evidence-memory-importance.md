# Amendment 002: Evidence Chain for Memory Importance

**Amendment ID:** `AMEND-002`
**Status:** `RATIFIED`
**Date:** `2026-07-22`
**Constitutional Articles Affected:** `Article III, Article IV`
**Laws Affected:** `memory.md, evidence.md`
**Sponsor:** `Architecture Council`

---

## Summary

Require that every memory importance score be backed by an evidence chain, making importance auditable and mutable only through evidence addition.

## Motivation

Memory importance scores currently lack evidence traceability. This amendment ensures that every importance score has a verifiable chain of evidence, making importance changes auditable and preventing arbitrary importance inflation.

## Changes

### Constitutional Changes

- **Article III, Section 4:** Add requirement that memory importance must be backed by evidence.

### Law Changes

- **`docs/laws/memory.md`:** Add "Every importance score must be backed by an evidence chain" to Evidence Requirements.
- **`docs/laws/evidence.md`:** Add memory importance to the list of evidence-supported fields. Add `importance_evidence` field to the evidence record schema.

## Impact

- **Backward Compatible:** `NO` — Existing memory fragments lack importance evidence chains.
- **Migration Required:** `YES` — Migration must create evidence chains for all existing memories based on their current importance scores.
- **Breaking Changes:** Memory importance computation must now produce and store evidence records.

## Migration Plan

1. Add `importance_evidence` field to `MemoryFragment`
2. Update `_score_memory` to create evidence records for importance
3. Write migration that iterates all existing memories and creates initial evidence chains
4. Update tests to verify importance evidence creation

## Ratification

- **Proposed:** `2026-07-22`
- **Ratified:** `2026-07-22`
- **Ratified By:** `Architecture Council`

## Supersession

- **Superseded By:** N/A
- **Superseded On:** N/A

---

*This amendment is governed by Article XIV of the IdentityOS Constitution.*
