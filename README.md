# IdentityOS

**The Open Identity Specification for AI**

> *Inspired by the anime Pluto — where every robot had its own unique soul.*

---

IdentityOS is a standard for **portable, versionable, persistent digital identities in AI systems**.

Just as HTTP enabled the web and Docker enabled containers, IdentityOS enables a world where:
- **Identities are portable** — run on any compliant runtime
- **Vendors compete on execution**, not lock-in
- **Users own** their AI relationships
- **Innovation happens at the runtime layer**, not the format layer

---

## Current Status: Foundation Complete, Ecosystem Building

**IdentityOS Architecture Foundation v1 is complete.**

The constitution, laws, amendment system, migration framework, goal engine, intention engine, evidence graph, and confidence system have all been implemented and verified.

**The architecture is now intentionally stable.** Future architectural work should arise from lessons learned while building real applications.

### What We're Building Now: [Runtime v2 — Real Agents](https://github.com/lacebx/IdentityOS/milestone/7)

| Project | Priority |
|---------|----------|
| Identity Chat | High |
| IdentityOS SDK | High |
| Public REST API | High |
| Identity Debugger | High |
| Browser Extension | High |
| Discord Agent | Medium |
| VSCode Extension | Medium |
| Identity Replay | Medium |
| Long-running Benchmark | Medium |
| Developer Examples | Medium |

Full roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Architecture

IdentityOS organizes identity state into **governed modules**, each with a constitutional foundation:

| Module | Constitution Article | Description |
|--------|-------------------|-------------|
| **Identity** | Article I | Core immutable properties (name, id, values) |
| **Truth** | Article II | Evidence-based fact model |
| **Memory** | Article III | Episodic and semantic memory with importance scoring |
| **Evidence** | Article IV | Immutable evidence chains with full provenance |
| **Evolution** | Article V | Mutation engine with FactStore-backed growth |
| **Preferences** | Article VI | Evidence-backed preference tracking |
| **Relationships** | Article VII | Trust-based relationship graph |
| **Goals** | Article VIII | Long-term objectives with lifecycle management |
| **Intentions** | Article IX | Short-term commitments with auto-expiry |
| **Timeline** | Article X | Append-only identity life story |
| **Sessions** | Article XI | Mode-detected session isolation |
| **Canonical Facts** | Article XII | FactStore as single source of truth |
| **Confidence** | Article XIII | Deterministic evidence-chain confidence |
| **Amendments** | Article XIV | Constitutional governance mechanism |

Full constitution: [docs/constitution/constitution-v1.md](docs/constitution/constitution-v1.md)

---

## Repository Structure

```
IdentityOS/
├── docs/                    ← Governance & planning
│   ├── constitution/        ← 14-article Identity Constitution
│   ├── laws/                ← 10 modular Identity Laws
│   ├── amendments/          ← Amendment records
│   ├── adr/                 ← Architecture Decision Records
│   └── ROADMAP.md           ← Current roadmap
│
├── core/                    ← Identity modules (constitution-compliant)
│   ├── identity.py          ← Identity core (immutable + mutable fields)
│   ├── memory.py            ← Memory store with importance scoring
│   ├── identity_facts.py    ← FactStore with evidence chains
│   ├── identity_mutation.py ← Evolution engine
│   ├── user_profile.py      ← User knowledge with confidence
│   ├── goals.py             ← Goal engine with lifecycle
│   ├── intentions/          ← Intention engine with auto-expiry
│   ├── evidence_graph.py    ← Evidence graph with provenance
│   ├── confidence/          ← Generalized confidence scorer
│   ├── relationships.py     ← Identity graph (trust networks)
│   ├── timeline.py          ← Append-only timeline
│   ├── migrations/          ← Schema migration framework
│   └── ...                  ← Other subsystems
│
├── runtime/                 ← IdentityOS runtime
│   ├── orchestrator.py      ← Identity lifecycle management
│   ├── persistence.py       ← Storage backends (JSON, SQLite, remote)
│   └── event_bus.py         ← Pub/sub event system
│
├── adapters/                ← Model adapters (Groq, OpenAI, Anthropic, Ollama)
├── sdk/                     ← Developer SDK (coming soon)
├── cli/                     ← Command-line interface
└── tests/                   ← Test suite
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### Setup

```bash
git clone https://github.com/lacebx/IdentityOS.git
cd IdentityOS
pip install -r runtime/requirements.txt
```

### CLI Quickstart

```bash
# Create an identity
python -m cli.main create --name "Lace" --persona mentor

# Start a session
python -m cli.main session --id lace

# Inspect identity state
python -m cli.main inspect --id lace
```

Full CLI documentation: [cli/README.md](cli/README.md)

### SDK Quickstart (Coming Soon)

```python
identity = Identity.load("lace")

response = identity.chat("Hello, how are you?")
goal = identity.goal(description="Learn Python", priority="high")
rel = identity.relationship("user-123", trust_level=0.8)
events = identity.timeline(limit=10)
identity.export("lace-portable.json")
```

---

## Roadmap

| Phase | Theme | Status |
|-------|-------|--------|
| **Phase 1** | Architecture Foundation | ✅ Complete |
| **Phase 2** | Runtime Ecosystem | 🔄 Active |
| **Phase 3** | Ecosystem Expansion | 📋 Planned |

Full roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Contributing

IdentityOS is an open standard. Contributions welcome in all forms.

### How to Contribute

1. **Fork** the repository
2. Create a **feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes
4. **Push** to the branch
5. Open a **Pull Request**

### What to Contribute

- **Applications** — Build on IdentityOS (Chat, Discord, VSCode, Browser)
- **SDK** — Help build the developer API
- **Documentation** — Examples, tutorials, guides
- **Tests** — Improve coverage
- **Adapters** — New LLM providers
- **Examples** — Demo projects

Full contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Governance

IdentityOS uses a **constitutional governance model**:

- **Constitution** — 14 articles defining fundamental principles
- **Laws** — 10 domain-specific laws with implementation requirements
- **Amendments** — Formal process for evolving the constitution
- **ADRs** — Architecture decision records for technical decisions

Changes to the architecture go through a formal amendment process. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Future Vision

### Marketplace

A future marketplace for identity components — constitutions, law packs, knowledge packs, skill packs, behavior packs, and more. Inclusion earned through demonstrated production usefulness. See [docs/future/MARKETPLACE_VISION.md](docs/future/MARKETPLACE_VISION.md) for the design document.

### Open Identity Foundation

Future community governance through an **Open Identity Foundation** — ensuring the specification remains vendor-neutral and community-driven.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

The Open Identity Specification is free to implement. No licensing fees.

---

## Questions?

**Q: Is this just a wrapper around ChatGPT?**  
No. IdentityOS defines a **standard** for portable AI identities. Any runtime can implement it.

**Q: Can I use this in production?**  
The architecture foundation is complete. Real-world validation through applications is the current focus.

**Q: Who controls the spec?**  
The community. Proposed governance: Open Identity Foundation (to be established).

**Q: How is this different from OpenAI's GPTs or Claude Projects?**  
Those are vendor-specific. IdentityOS identities are **portable** — they can run on any compliant runtime.

---

**IdentityOS** — The infrastructure for persistent AI identities.

*Every AI deserves its own soul.*
