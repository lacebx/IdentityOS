# ADR-001: Modular FactStore Over Knowledge Graph

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** Article IV (Evidence)

---

## Context

The system needs to store knowledge about the user and the identity. Options include a full knowledge graph, relational database, or simple key-value store with evidence chains.

## Decision

Use a modular FactStore pattern where each identity entity owns a `FactStore` that records facts with full evidence chains. The `FactStore` is key-value with conflict detection, not a graph. For graph operations (relationships), a separate `IdentityGraph` is used.

## Rationale

1. **Simplicity** — A full knowledge graph is overengineered for the current use case. Most operations are simple CRUD on typed facts.
2. **Evidence chains** — The FactStore's append-only evidence model is the foundation for all confidence computation.
3. **Session isolation** — Forking a FactStore is trivial (copy-on-write list); forking a graph database is not.
4. **Relationship exceptions** — A separate IdentityGraph handles graph operations where they add value (trust networks, relationship queries).

## Consequences

- Positive: Simple, auditable, easy to serialize/deserialize
- Positive: Session fork/merge is straightforward
- Negative: Multi-hop relationship queries require the separate IdentityGraph
- Negative: Not suitable for large-scale entity-relationship queries without the graph component

## Compliance

- `core/user_profile.py` — UserProfile implements FactStore with evidence chains
- `core/identity_facts.py` — FactStore with full evidence support
- `core/identity_graph.py` — IdentityGraph for relationship edges
