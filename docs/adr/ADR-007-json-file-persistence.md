# ADR-007: JSON File Persistence Over Database

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** N/A (Infrastructure)

---

## Context

The system needs to persist identity state, memories, facts, sessions, and timeline across restarts. Options include SQLite, PostgreSQL, file-based JSON, or a document database.

## Decision

Use JSON file persistence. Each subsystem (identity, memory, goals, intentions, timeline) persists to its own JSON file in a designated data directory.

## Rationale

1. **Simplicity** — JSON files require no database server, no connection pooling, no schema migrations.
2. **Debuggability** — JSON files can be read, edited, and inspected with any text editor or `jq`.
3. **Portability** — The entire identity state is a directory of JSON files. Copy, backup, migrate by copying a directory.
4. **Adequate scale** — For a single-identity personal assistant, JSON files are more than adequate. The entire identity state fits in memory.
5. **Auditability** — Git can track JSON file changes, providing version history.

## Consequences

- Positive: Zero infrastructure dependencies
- Positive: Easy debugging and inspection
- Positive: Simple backup and migration
- Negative: Not suitable for multi-user, high-concurrency, or large-scale deployments
- Negative: No query capabilities — all data must be loaded into memory
- Negative: Write performance degrades with file size (full file rewrite on each change)

## Compliance

- `runtime/orchestrator.py` — `_persist_memories()`, `_load_persisted_memories()`
- Core subsystems: identity, memory, goal, intention, timeline persistence
- Data directory configuration in `IdentityConfig`
