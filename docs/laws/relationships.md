# Relationships Law

**Domain:** Relationships
**Constitutional Basis:** Article VII

---

## Purpose

Govern how identities form, maintain, and evolve relationships with users, other identities, and external entities.

## Responsibilities

- Track relationship edges between identities
- Manage trust levels and relationship strength
- Record interaction frequency
- Extract relationship facts from conversation
- Provide relationship context to the LLM

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create edge | Yes | Through interaction or API |
| Update trust | Yes | Through repeated positive interaction |
| Update strength | Yes | Through interaction frequency |
| Update context | Yes | On each interaction |
| Delete edge | Yes | Through API or identity unload |

## Conflict Resolution

- Relationship facts extracted from conversation go into UserProfile, not memory
- The IdentityGraph manages directional edges; cycles are allowed
- Trust level decays slowly without interaction

## Evidence Requirements

- Every relationship edge records its creation timestamp
- Every interaction updates last_interaction and interaction_count
- Relationship extraction from user input must match defined regex patterns

## Lifecycle

1. **Discovery** — User mentions a relationship; extractor captures it
2. **Storage** — Stored in UserProfile for the session
3. **Graph Edge** — An edge is created in IdentityGraph
4. **Evolution** — Trust and strength evolve through interaction
5. **Decay** — Inactive relationships lose strength over time

## Examples

```python
# Extraction from user input
extract_user_facts("Alice is my sister")
# → UserFact(field="relationships.sister", value="Alice")

# Graph connection
identity_graph.connect(
    source_id="lace",
    target_id="alice",
    edge_type=EdgeType.FAMILY,
    trust_level=TrustLevel.HIGH,
)
```

## Future Extensions

- Relationship inference (e.g., "sister's husband" → brother-in-law)
- Relationship graph visualization
- Multi-hop relationship queries
