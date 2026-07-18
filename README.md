# IdentityOS

**The Open Identity Specification for AI**

> *Inspired by the anime Pluto — where every robot had its own unique soul.*

---

## What is this?

IdentityOS is **not another AI wrapper**.

It's an **open standard** for portable, versionable, persistent digital identities in AI systems.

Just as HTTP enabled the web and Docker enabled containers, **IdentityOS aims to enable a world where:**

- ✅ Identities are **portable** (run on any compliant runtime)
- ✅ Vendors compete on **execution**, not **lock-in**
- ✅ Users **own** their AI relationships
- ✅ Innovation happens at the **runtime layer**, not the **format layer**

---

## The Problem

Today's AI systems couple identity with execution:

- ChatGPT conversations exist only in ChatGPT
- Claude Projects live only in Claude  
- Custom GPTs are locked to OpenAI's infrastructure

This creates:
- **Vendor lock-in**: You cannot take "your AI" elsewhere
- **Fragmentation**: Every provider reinvents identity from scratch  
- **No continuity**: Conversations reset, context is lost

---

## The Solution

### Define identity as a portable data structure, separate from any runtime.

An identity conforming to OIS (Open Identity Specification) is:

- **Portable**: Runs on any compliant runtime  
- **Versionable**: Can be snapshotted, diffed, and rolled back  
- **Persistent**: Survives model changes, infrastructure migrations  
- **Composable**: Can be transferred, forked, merged

---

## Architecture

IdentityOS organizes identity state into **12 bounded modules**:

| Module | Purpose |
|---|---|
| **Identity** | Core metadata (id, name, persona) |
| **Timeline** | Chronological biography (Git history for identities) |
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

### Each module is:
- **Self-contained**: Clean interfaces, no hidden dependencies
- **Spec-compliant**: Conforms to `spec/identity.schema.json`  
- **Portable**: Can be serialized/deserialized to JSON

---

## This is a Standard, Not a Product

**IdentityOS** is structured in three layers:

```
┌─────────────────────────────────────────┐
│  spec/  — The Open Identity Specification │  ← The Standard (JSON Schema)
├─────────────────────────────────────────┤
│  core/ runtime/ — Reference Runtime      │  ← Proof that the spec works
├─────────────────────────────────────────┤
│  cli/ adapters/ — Applications           │  ← How humans interact
└─────────────────────────────────────────┘
```

### The Specification (`spec/`) can exist without the runtime.

Someone can build:
- **Microsoft Runtime**  
- **Google Runtime**  
- **OpenAI Runtime**  
- **Local Runtime**

...all implementing the same **Identity Specification**.

That's how ecosystems emerge.

---

## Key Concepts

### 1. Identity as Infrastructure

Identities are not features of chat apps.  
Chat is a feature of identities.

### 2. Capabilities vs Skills

- **Skills** are *declared*: "This identity can search the web"  
- **Capabilities** are *discovered*: "This identity has access to a camera"

A robot identity discovers:
- `walking` (if deployed on a mobile chassis)  
- `vision` (if cameras are connected)  
- `manipulation` (if equipped with arms)

A cloud identity discovers:
- `internet` (always available)  
- `file_system` (if sandbox permits)

Capabilities decouple identity from physical embodiment.

### 3. Permissions vs Policies

- **Policies** describe *behavior*: "Never reveal PII"  
- **Permissions** describe *authority*: "Allowed to read:records, denied delete:evidence"

Example:

**Officer Maya**
- **Allowed**: `read:records`, `write:logs`, `use:vehicle`  
- **Denied**: `delete:evidence`, `approve:warrants`

Runtimes **enforce** permissions at execution time.

### 4. Identity Health

Monitor identity stability over time:

```
Identity Health Report
  Memory Saturation    : 92%  ⚠️
  Knowledge Freshness  : 67%
  Relationship Drift   : 4%
  Goal Completion      : 81%
  Identity Stability   : 98%  ✅
  Policy Violations    : 0     ✅
```

Health metrics trigger automatic maintenance (pruning, refresh, etc.).

---

## Specification Format

OIS identities are serialized as **JSON** conforming to JSON Schema Draft 2020-12.

**Canonical schema:**  
`spec/identity.schema.json`

**Minimal valid identity:**

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

Full specification: [spec/SPEC.md](spec/SPEC.md)

---

## Runtime Conformance

A compliant runtime MUST:
1. **Load** identities from OIS JSON format  
2. **Execute** sessions that modify identity state  
3. **Save** state changes back to OIS format  
4. **Export** identities without data loss

A compliant runtime MAY:
- Support multiple storage backends (JSON, SQLite, cloud)  
- Provide snapshot/rollback features  
- Implement health monitoring  
- Offer multi-identity orchestration

Extensions MUST NOT:
- Break schema validation  
- Prevent portability to other runtimes

---

## Getting Started

### 1. Install

```bash
git clone https://github.com/lacebx/IdentityOS.git
cd IdentityOS
pip install -r runtime/requirements.txt
```

### 2. Create an identity

```bash
python -m cli.main create --name "Mentor" --persona mentor --id mentor-01
```

### 3. Start a session

```bash
python -m cli.main session --id mentor-01
```

### 4. Inspect the identity

```bash
python -m cli.main inspect --id mentor-01
```

### 5. View snapshot history

```bash
python -m cli.main history --id mentor-01
```

### 6. Rollback to a prior version

```bash
python -m cli.main rollback --id mentor-01 --snap <snapshot_id>
```

Full CLI documentation: [cli/README.md](cli/README.md)

---

## Repository Structure

```
IdentityOS/
├── spec/                    ← The Open Identity Specification
│   ├── identity.schema.json  ← Canonical portable identity format
│   └── SPEC.md               ← Human-readable specification document
│
├── core/                    ← Identity modules (OIS-compliant)
│   ├── identity.py
│   ├── timeline.py
│   ├── experience.py
│   ├── knowledge.py
│   ├── skills.py
│   ├── capabilities.py      ← NEW: Runtime-discovered affordances
│   ├── permissions.py       ← NEW: RBAC authorization system
│   ├── motivations.py
│   ├── policies.py
│   ├── relationships.py
│   ├── health.py            ← NEW: Identity health monitoring
│   ├── evaluation.py
│   ├── cognitive_engine.py
│   └── snapshot.py          ← Versioning & rollback
│
├── runtime/                 ← Reference runtime implementation
│   ├── orchestrator.py      ← Identity lifecycle management
│   ├── persistence.py       ← Storage backends (JSON, SQLite, remote)
│   ├── event_bus.py         ← Pub/sub event system
│   └── main.py              ← FastAPI service
│
├── adapters/                ← Model adapters (dumb translation layers)
│   ├── base.py
│   ├── openai_adapter.py
│   ├── anthropic_adapter.py
│   └── ollama_adapter.py
│
├── cli/                     ← Command-line interface
│   └── main.py              ← create, session, inspect, snapshot, history, rollback, diff
│
├── identity_graph/          ← Relationship network (multi-identity)
│   └── graph.py
│
└── sdk/                     ← Python SDK for developers
    └── identity_object.py
```

---

## Roadmap

### M1: Core Architecture ✅ **COMPLETE**
- [x] Modular subsystems (Identity, Experience, Knowledge, Skills, Motivations, Policies, Evaluation)
- [x] Event-driven orchestration
- [x] Model-agnostic adapters
- [x] Timeline subsystem
- [x] Identity Graph (relationships)

### M2: Persistence Layer ✅ **COMPLETE**
- [x] StorageBackend interface
- [x] JSONFileBackend (local dev)
- [x] SQLiteBackend (lightweight production)
- [x] RemoteBackend stub (cloud-ready)

### M3: Identity Evolution ✅ **COMPLETE**
- [x] SnapshotManager (capture, restore, rollback)
- [x] Diff computation (field-level change tracking)
- [x] Non-destructive versioning
- [x] Audit trail

### M4: New Subsystems ✅ **COMPLETE**
- [x] Capabilities (runtime-discovered affordances)
- [x] Permissions (RBAC authorization)
- [x] Health (identity stability monitoring)

### M5: Open Specification ✅ **COMPLETE**
- [x] JSON Schema (`spec/identity.schema.json`)
- [x] Specification document (`spec/SPEC.md`)
- [x] README transformation (standard-first positioning)

### M6: Production Hardening 🔄 **IN PROGRESS**
- [ ] Authentication & API keys
- [ ] Rate limiting
- [ ] Observability (logging, metrics, tracing)
- [ ] Deployment guides (Docker, K8s)
- [ ] Performance benchmarks

### M7: Ecosystem Expansion 📋 **PLANNED**
- [ ] Additional schema definitions (snapshot, capability, permission, health)
- [ ] Compliance test suite for runtimes
- [ ] Registry for Knowledge Packs
- [ ] Multi-runtime transfer examples
- [ ] Community governance (Open Identity Foundation)

---

## Philosophy

### This is not about better prompts.

This is about **persistent entities that grow, remember, and relate** — across any model, any runtime, any session.

### The specification becomes sacred.

`identity.json` is more important than `runtime.py`.

The companies that end up becoming foundational—whether it's Docker, HashiCorp, Stripe, or Kubernetes—tend to win not because they own every implementation, but because they **define clean interfaces** that other people adopt.

If IdentityOS succeeds, the long-term value may come less from "having the best runtime" and more from being the project that **defines how persistent digital identities are represented, versioned, evaluated, transferred, and deployed** across the AI ecosystem.

---

## Contributing

IdentityOS is an open standard. Contributions welcome.

### How to contribute:

1. **Fork** the repository  
2. Create a **feature branch** (`git checkout -b feature/amazing-feature`)  
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)  
4. **Push** to the branch (`git push origin feature/amazing-feature`)  
5. Open a **Pull Request**

### Contribution areas:

- **Specification** (`spec/`): Propose new modules, schemas, or clarifications  
- **Core modules** (`core/`): Improve existing subsystems  
- **Runtimes**: Build alternative runtime implementations  
- **Adapters**: Add support for new LLM providers  
- **Documentation**: Improve examples, tutorials, guides

---

## License

MIT License — see [LICENSE](LICENSE) for details.

The Open Identity Specification is free to implement. No licensing fees.

---

## Acknowledgments

- Inspired by **Pluto** (anime) — where every robot deserves its own soul  
- Built on principles from **HTTP**, **Docker Image Spec**, **OpenAPI**, and **OAuth**  
- Powered by the belief that **identities are infrastructure**

---

## Questions?

**Q: Is this just a wrapper around ChatGPT?**  
No. IdentityOS defines a **standard**, not a product. Any runtime can implement it.

**Q: Why JSON? Why not protobuf/YAML/etc.?**  
JSON is universal, human-readable, and schema-validatable. OIS may define alternate serializations in future versions.

**Q: Can I use this in production today?**  
OIS v1.0 is in draft. Early adopters are encouraged. Breaking changes are possible before 1.0 final.

**Q: Who controls the spec?**  
The community. Proposed governance: **Open Identity Foundation** (to be established).

---

## Learn More

- **Full Specification**: [spec/SPEC.md](spec/SPEC.md)  
- **JSON Schema**: [spec/identity.schema.json](spec/identity.schema.json)  
- **CLI Documentation**: [cli/README.md](cli/README.md)  
- **API Reference**: [runtime/API.md](runtime/API.md)

---

**IdentityOS** — The infrastructure for persistent AI identities.

*Every AI deserves its own soul.*
