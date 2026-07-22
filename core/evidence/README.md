# Evidence Graph

**Path:** `core/evidence_graph.py`

## Overview

A generic graph that connects evidence nodes to any entity (facts, goals, intentions, memories, relationships). Provides full provenance tracking and confidence computation.

## Key Classes

- **`EvidenceNode`** — A piece of evidence (conversation, evaluation, user statement, etc.)
- **`EvidenceEdge`** — A directed edge connecting an entity to its evidence
- **`EvidenceGraph`** — Manages nodes and edges with query methods

## Evidence Types

`CONVERSATION`, `EVALUATION`, `USER_STATEMENT`, `ASSISTANT_STATEMENT`, `CREATOR_DEFINED`, `RUNTIME_INFERRED`, `POLICY_CHECK`

## Key Methods

- `add_node(node)` / `add_edge(edge)` — Add evidence
- `connect(fact_id, evidence_id)` — Link entity to evidence
- `evidence_for(entity_id)` — Get all evidence for an entity
- `provenance(entity_id)` — Full provenance with confidence
- `confidence_for(entity_id)` — Computed confidence from evidence chain

## Design

The graph is entity-ID-agnostic — any knowledge object can be linked to evidence via its unique ID. No schema coupling between evidence and entity types.

## Serialization

`EvidenceGraph` supports `to_dict()` / `from_dict()`.
