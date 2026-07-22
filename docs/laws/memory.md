# Memory Law

**Domain:** Memory
**Constitutional Basis:** Article III

---

## Purpose

Govern how memories are created, stored, retrieved, and decayed. Memory is strictly separated from identity and knowledge.

## Responsibilities

- Store episodic, semantic, core, and working memories
- Assign and maintain importance scores for each memory
- Support multi-factor retrieval (importance + keyword + recency + identity relevance)
- Persist memories to durable storage
- Load memories on identity load

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create | Yes | Always, through interaction pipeline |
| Read | Yes | Always, through memory store API |
| Update importance | Yes | Reinforcement or decay |
| Delete | Yes | Only through explicit memory clearing |
| Bulk clear | Yes | Only through explicit API call |

## Conflict Resolution

- Memory importance scoring uses a multi-factor formula: importance × 3 + keyword overlap + recency bonus + identity reference + tag bonus
- When two memories conflict, the one with higher importance and recency wins retrieval priority
- Contradictory memories are not deleted — they compete on retrieval score

## Evidence Requirements

- Every memory must have a source (conversation, API, extraction)
- Every memory must have a memory type (core, semantic, episodic, working)
- Importance should be auto-computed on creation but may be set explicitly

## Lifecycle

1. **Creation** — Memory fragment created with content, type, importance
2. **Storage** — Added to in-memory store and persisted to durable store
3. **Retrieval** — Scored and ranked at query time
4. **Reinforcement** — Access increases access_count, may promote importance
5. **Decay** — Unaccessed memories may have importance reduced over time
6. **Deletion** — Removed on explicit request or memory clearing

## Examples

```python
frag = make_memory(
    "My daughter Emma is my world.",
    has_relationship=True,
    is_emotional=True,
)
# importance auto-computed to ~0.37

# Retrieval scoring
_score = _score_memory(frag, query="daughter")
# returns importance × 3 + keyword matches + recency + identity refs
```

## Future Extensions

- Background importance decay process
- Memory consolidation (episodic → semantic promotion)
- Cross-identity memory sharing
