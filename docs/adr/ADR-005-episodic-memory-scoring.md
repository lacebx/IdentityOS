# ADR-005: Episodic Memory with Importance Scoring Over Vector Embeddings

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** Article III (Memory)

---

## Context

The system needs to retrieve relevant memories for context injection. Options include vector embeddings with semantic similarity, keyword-based retrieval, or a hybrid approach with importance scoring.

## Decision

Use multi-factor scoring for memory retrieval: importance × keyword overlap + recency bonus + identity reference + tag bonus. No vector embeddings are used.

## Rationale

1. **Determinism** — Keyword + importance scoring is deterministic and auditable, matching the constitutional preference for transparency.
2. **Constitutional compliance** — Article III requires that memory importance be meaningful and influence retrieval.
3. **No external service** — Vector embeddings require an embedding model or API call, introducing latency and cost.
4. **Proven approach** — The existing implementation (`_score_memory`) has been tested and works reliably.

## Consequences

- Positive: Zero external dependencies for memory retrieval
- Positive: Fast, deterministic, auditable
- Positive: Importance scoring directly influences retrieval, making the system preference-aware
- Negative: Cannot capture semantic similarity (e.g., "my kid" vs "my daughter" are different keywords)
- Negative: Long-term, vector embeddings may be needed for cross-lingual or paraphrase-tolerant retrieval

## Compliance

- `core/memory.py` — `_score_memory()`, `_query_relevant_memories()`
