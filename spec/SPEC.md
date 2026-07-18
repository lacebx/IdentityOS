# The Open Identity Specification for AI

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2026-07-18

---

## Abstract

This document defines **The Open Identity Specification** (OIS), a portable, versionable, and runtime-agnostic format for persistent digital identities in AI systems. 

Inspired by foundational standards like HTTP, Docker Image Spec, and OpenAPI, OIS defines **what an identity is**, not **how it runs**. Any compliant runtime—whether built by Microsoft, Google, OpenAI, or an independent developer—can load, execute, and evolve identities that conform to this specification.

**Core Principle:**  
Identities are infrastructure. They persist across models, runtimes, and sessions.

---

## 1. Introduction

### 1.1 Problem Statement

Today's AI systems couple identity with execution:
- ChatGPT conversations exist only in ChatGPT
- Claude Projects live only in Claude
- Custom GPTs are locked to OpenAI's infrastructure

This creates:
- **Vendor lock-in**: You cannot take "your AI" elsewhere
- **Fragmentation**: Every provider reinvents identity from scratch
- **No continuity**: Conversations reset, context is lost

### 1.2 Solution

Define identity as a **portable data structure** separate from any runtime.

An identity conforming to OIS is:
- **Portable**: Runs on any compliant runtime
- **Versionable**: Can be snapshotted, diffed, and rolled back
- **Persistent**: Survives model changes, infrastructure migrations
- **Composable**: Can be transferred, forked, merged

### 1.3 Design Philosophy

1. **Specification over implementation**  
   OIS defines the format; runtimes compete on execution quality.

2. **Standards enable ecosystems**  
   Docker didn't win by having the best container engine. It won by defining the container image format.

3. **Identity as first-class primitive**  
   Identity is not a feature of a chat app. Chat is a feature of an identity.

---

## 2. Core Concepts

### 2.1 Identity

An **identity** is a persistent digital entity with:
- **Metadata**: id, name, persona
- **State**: experience, knowledge, motivations
- **Behavior**: skills, policies, permissions
- **History**: timeline, snapshots, evolution

### 2.2 Modules

OIS organizes identity state into **bounded subsystems**:

| Module | Purpose |
|---|---|
| **Identity** | Core metadata (id, name, persona) |
| **Timeline** | Chronological biography |
| **Experience** | Accumulated interactions and memories |
| **Knowledge** | Domain-specific declarative knowledge |
| **Skills** | Executable capabilities (tools, APIs) |
| **Capabilities** | Physical/environmental affordances (vision, speech, locomotion) |
| **Permissions** | Authorization scopes (what the identity is *allowed* to do) |
| **Motivations** | Goals, drives, priorities |
| **Policies** | Behavioral constraints and rules |
| **Relationships** | Graph of connections to other identities/entities |
| **Health** | Observable metrics (saturation, stability, drift) |
| **Evaluation** | Performance reports and feedback |

### 2.3 Snapshots

A **snapshot** is a point-in-time capture of all module states.

Snapshots enable:
- **Versioning**: Track identity evolution over time
- **Rollback**: Restore prior states non-destructively
- **Diff**: Compare changes between any two snapshots
- **Audit**: Full history of who the identity was at each moment

### 2.4 Runtimes

A **runtime** is any system that:
1. Loads an OIS-compliant identity
2. Executes interactions (sessions, tasks, evaluations)
3. Persists state changes back to the identity format

Runtimes compete on:
- Model quality
- Orchestration efficiency
- Storage backends
- User experience

Runtimes must NOT:
- Lock identities to proprietary formats
- Prevent export or migration

---

## 3. Specification Format

### 3.1 Serialization

OIS identities are serialized as **JSON** conforming to the JSON Schema Draft 2020-12.

Canonical schema:  
`https://identity-spec.org/schemas/v1/identity.json`

### 3.2 Required Fields

```json
{
  "spec_version": "1.0",
  "identity": {
    "id": "unique-identifier",
    "name": "Human-Readable Name"
  },
  "created_at": 1689724800.0
}
```

### 3.3 Full Example

See `identity.schema.json` for the complete formal definition.

Minimal valid identity:

```json
{
  "spec_version": "1.0",
  "identity": {
    "id": "mentor-01",
    "name": "Mentor AI",
    "persona": "mentor"
  },
  "created_at": 1689724800.0,
  "timeline": {"events": []},
  "experience": {"entries": []},
  "knowledge": {"packs": []},
  "skills": {"available": []},
  "capabilities": {"available": []},
  "permissions": {"allowed": [], "denied": []},
  "motivations": {"active": []},
  "policies": {"rules": []},
  "relationships": {"nodes": [], "edges": []},
  "health": {},
  "evaluation": {"reports": []}
}
```

---

## 4. Module Specifications

### 4.1 Timeline

**Purpose:** Chronological event log forming the identity's biography.

**Schema:**
```json
"timeline": {
  "events": [
    {
      "timestamp": 1689724800.0,
      "event_type": "message",
      "data": {"content": "First interaction"},
      "significance": 0.8
    }
  ]
}
```

**Design Notes:**
- Timeline is append-only
- `significance` (0-1) indicates event importance
- Major events (goal achieved, policy violation) have high significance

---

### 4.2 Capabilities

**Purpose:** Physical or environmental capabilities the identity can access.

**Schema:**
```json
"capabilities": {
  "available": [
    {
      "name": "vision",
      "enabled": true,
      "provider": "device:camera-01"
    },
    {
      "name": "walking",
      "enabled": false
    }
  ]
}
```

**Design Notes:**
- Capabilities are **discovered** at runtime, not declared
- A robot identity discovers `walking` if deployed on a mobile chassis
- A cloud identity discovers `internet` but not `walking`
- Capabilities decouple identity from physical embodiment

---

### 4.3 Permissions

**Purpose:** Authorization scopes defining what the identity is allowed to do.

**Schema:**
```json
"permissions": {
  "allowed": ["read:records", "write:logs"],
  "denied": ["delete:evidence"],
  "roles": ["officer", "analyst"]
}
```

**Design Notes:**
- Permissions describe **authority**, not behavior
- Policies describe behavior; permissions describe authorization
- Runtimes enforce permissions at execution time

---

### 4.4 Health

**Purpose:** Observable metrics for monitoring identity stability.

**Schema:**
```json
"health": {
  "memory_saturation": 0.92,
  "knowledge_freshness": 0.67,
  "relationship_drift": 0.04,
  "goal_completion": 0.81,
  "identity_stability": 0.98,
  "policy_violations": 0,
  "last_evaluated": 1689724800.0
}
```

**Design Notes:**
- All metrics are normalized to [0, 1] except `policy_violations`
- High `memory_saturation` triggers pruning
- Low `knowledge_freshness` triggers refresh
- `relationship_drift` measures graph stability

---

## 5. Snapshot Format

Snapshots wrap the identity state with metadata:

```json
{
  "snapshot_id": "uuid",
  "identity_id": "mentor-01",
  "captured_at": 1689724800.0,
  "label": "after-session-3",
  "schema_version": "1.0.0",
  "modules": {
    "identity": {...},
    "timeline": {...},
    "experience": {...},
    ...
  },
  "meta": {
    "triggered_by": "user",
    "reason": "manual checkpoint"
  }
}
```

---

## 6. Runtime Conformance

### 6.1 Mandatory Capabilities

A compliant runtime MUST:
1. **Load** identities from OIS JSON format
2. **Execute** sessions that modify identity state
3. **Save** state changes back to OIS format
4. **Export** identities without data loss

### 6.2 Optional Capabilities

A compliant runtime MAY:
- Support multiple storage backends (JSON, SQLite, cloud)
- Provide snapshot/rollback features
- Implement health monitoring
- Offer multi-identity orchestration

### 6.3 Extensions

Runtimes may add custom fields under:
- `identity.metadata`
- `meta` (in snapshots)
- Module-level `metadata` objects

Extensions MUST NOT:
- Break schema validation
- Prevent portability to other runtimes

---

## 7. Interoperability

### 7.1 Identity Transfer

Identities can be transferred between runtimes by:
1. Exporting the latest snapshot as JSON
2. Importing into the target runtime
3. Resuming execution

### 7.2 Knowledge Packs

Knowledge is modular. Packs have:
- `name`, `version`, `source`, `checksum`
- Packs can be published to registries
- Identities declare dependencies

### 7.3 Skill Manifests

Skills define callable interfaces:
```json
{
  "name": "search_documents",
  "type": "function",
  "enabled": true,
  "config": {
    "endpoint": "https://api.example.com/search",
    "auth": "bearer_token"
  }
}
```

---

## 8. Security & Privacy

### 8.1 Permissions Enforcement

Runtimes MUST enforce `permissions.allowed` and `permissions.denied`.

### 8.2 Data Sovereignty

Identities belong to their creators. Runtimes MUST NOT:
- Claim ownership of identity data
- Prevent export or deletion
- Mine identity data without consent

### 8.3 Encryption

OIS defines the format, not the transport.

Runtimes SHOULD:
- Encrypt identities at rest
- Use TLS for transfer
- Support key-based identity access control

---

## 9. Governance

### 9.1 Versioning

OIS uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes to required fields
- **MINOR**: New optional modules or fields
- **PATCH**: Documentation, examples, clarifications

### 9.2 Evolution

Changes to OIS follow:
1. Proposal (GitHub issue)
2. Discussion (community feedback)
3. Draft spec update
4. Reference implementation
5. Release

### 9.3 Stewardship

OIS is stewarded by the **Open Identity Foundation** (proposed).

Any organization may implement OIS. No licensing fees.

---

## 10. Reference Implementation

The reference runtime is **IdentityOS Runtime**:  
https://github.com/lacebx/identity-runtime

Features:
- Full OIS v1.0 support
- JSON + SQLite storage backends
- Snapshot/rollback
- CLI + FastAPI
- Model-agnostic (OpenAI, Anthropic, Ollama)

---

## 11. FAQ

**Q: Is this just a wrapper around ChatGPT?**  
No. OIS defines a **standard**, not a product. Any runtime can implement it.

**Q: Why JSON? Why not protobuf/YAML/etc.?**  
JSON is universal, human-readable, and schema-validatable. OIS may define alternate serializations in future versions.

**Q: Can I use this in production today?**  
OIS v1.0 is in draft. Early adopters are encouraged. Breaking changes are possible before 1.0 final.

**Q: Who controls the spec?**  
The community. Proposed governance: Open Identity Foundation (to be established).

---

## 12. Conclusion

The Open Identity Specification defines **infrastructure for persistent AI identities**.

Just as HTTP enabled the web and Docker enabled containers, OIS aims to enable a world where:

- Identities are portable
- Vendors compete on execution, not lock-in
- Users own their AI relationships
- Innovation happens at the runtime layer, not the format layer

**This is not about better prompts.**  
**This is about persistent entities that grow, remember, and relate—across any model, any runtime, any session.**

---

## Appendix A: Schema Index

- `identity.schema.json` — Core identity format
- `snapshot.schema.json` — Snapshot envelope format (TBD)
- `capability.schema.json` — Capability manifest (TBD)
- `permission.schema.json` — Permission policy format (TBD)
- `health.schema.json` — Health metrics format (TBD)

---

## Appendix B: References

- JSON Schema: https://json-schema.org/
- Semantic Versioning: https://semver.org/
- Docker Image Spec: https://github.com/opencontainers/image-spec
- OpenAPI Specification: https://spec.openapis.org/
