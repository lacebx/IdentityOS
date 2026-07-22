# Identity Law

**Domain:** Identity Core
**Constitutional Basis:** Article I

---

## Purpose

Define the immutable and mutable properties of an identity, and govern how identity fields may change over time.

## Responsibilities

- Maintain the identity's immutable core (name, id, class, values)
- Manage mutable identity fields (role, persona, communication style)
- Enforce field-level mutability constraints
- Provide versioning and snapshot capability
- Ensure the identity can be serialized, persisted, and restored

## Allowed Mutations

| Field | Mutability | Allowed Operations |
|-------|-----------|-------------------|
| name | LOCKED | None |
| id | LOCKED | None |
| identity_class | LOCKED | None |
| core_values | LOCKED | None (values are set at creation) |
| role | MUTABLE | Update via mutation engine |
| persona | MUTABLE | Update via mutation engine |
| communication_style | MUTABLE | Update via mutation engine |
| traits | EVOLVABLE | Add, update, remove via mutation engine |
| preferences | EVOLVABLE | Via FactStore mutation only |
| beliefs | EVOLVABLE | Via FactStore mutation only |

## Conflict Resolution

- Attempts to mutate a LOCKED field must be rejected before the LLM processes the input
- The orchestrator's identity mutation gate is the enforcement point
- Mutations to EVOLVABLE fields must go through the mutation engine, which validates against the FactStore

## Evidence Requirements

- Core identity fields require no evidence (they are set at creation)
- Mutable field changes require a proposal from the mutation engine
- EVOLVABLE field changes require evidence chain entries in the FactStore

## Lifecycle

1. **Creation** — Identity is created with immutable core + initial mutable fields
2. **Active** — Identity interacts, may evolve through mutations
3. **Version Bump** — Each accepted mutation bumps the patch version
4. **Snapshot** — Version history records snapshots at each bump
5. **Archived** — Identity may be archived (status = archived)

## Examples

```python
identity = create_identity("Lace", identity_class=IdentityClass.AGENT)
identity.is_field_locked("name")  # True
identity.is_field_locked("role")  # False

# Attempt to rename
detect_identity_rename_attempt("Your name is Bob")  # Returns "Bob"
# Gate blocks: "My name is Lace. I cannot be renamed."
```

## Future Extensions

- Field-level mutability overrides via constitutional amendment
- Multi-identity branching and merging
- Identity templates
