# IdentityOS

**Your AI should know you — not just your conversation history.**

> IdentityOS is a runtime for persistent AI identities that reason across apps, time, and decisions. It's not shared memory. It's a living assistant that notices what you don't.

---

## One-minute demo

```bash
git clone https://github.com/lacebx/IdentityOS.git
cd IdentityOS
bash demo.sh
```

Watch the identity learn a goal in ChatGPT, learn a conflicting decision in Discord, and proactively flag the broken plan in a third workspace — without being asked.

---

## What IdentityOS proves that no isolated AI can

| App | What it knows | What it misses |
|-----|--------------|----------------|
| ChatGPT | Your promotion depends on shipping a project | The project was cancelled |
| Discord | The project was cancelled | Why it mattered |
| **IdentityOS** | **Both. And it connects them.** | |

The identity doesn't just remember. It infers dependencies, detects blocked goals, and intervenes before you realize a plan is broken.

---

## Architecture

```
                         Identity OS
                             |
      -------------------------------------------------
      |                       |                       |
 Identity Registry         Memory Layer          Capability Marketplace
 (Who am I?)              (What do I know?)      (What can I do?)
      |                       |                       |
  registry/index.json     MemoryStore              CapabilityRegistry
  manifest.json           UserProfile              SkillPack
  tools/identity          TimelineRegistry         permissions system
                          FactStore
                          extract_user_facts()
```

Three orthogonal concerns, one runtime. Identities are publishable, memory is portable, capabilities are installable. Each pillar can evolve independently.

---

## Current milestone: Capability Marketplace

We proved cross-app reasoning. Now we're making identities extensible.

**Next up:** An identity that can install skills like `identity.github.analyze` or `identity.calendar.summarize` — acquiring new abilities without retraining or code changes.

See open issues: [Capability Marketplace](https://github.com/lacebx/IdentityOS/issues/38)

---

## Quick start for contributors

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run all tests
python3 -m pytest tests/ -q

# Run the demo
bash demo.sh
```

Start here: [Good first issues](https://github.com/lacebx/IdentityOS/labels/good%20first%20issue)

---

## Architecture

IdentityOS organizes identity state into **governed modules**, each with a constitutional foundation:

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

### SDK Quickstart

```python
from identityos import Identity

agent = Identity.create("MyBot")
agent.observe("My name is Alice and I love Python")
agent.goal("Master FastAPI", priority="high")
agent.relationship("mentor", trust_level=0.9)
agent.export("mybot.json")        # portable — share, move, restore
# Restore: restored = Identity.from_file("mybot.json")
```

```python
# Output:
# Facts learned: ['name', 'preferences.likes.python']
# Goals: [('Master FastAPI', 'HIGH')]
```

No API key required for identity features (facts, goals, relationships, memory, export). Add an adapter for chat — see [adapters](adapters/).

---

## Try It Now

Start the runtime server, then copy-paste these curl commands to see identity context injection in action:

```bash
# Terminal 1: Start the runtime server
source /tmp/identityos-venv/bin/activate
setsid python -m runtime.main > /tmp/runtime-server.log 2>&1 &

# Terminal 2: Create an identity
curl -s -X POST http://localhost:8000/identity \
  -H "Content-Type: application/json" \
  -d '{"identity_id":"pluto","name":"Pluto","persona":"A loyal robot companion"}'

# Get augmented context for prompt injection (inject into ChatGPT/Grok)
curl -s -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!","identity_id":"pluto","user_id":"me"}'

# Store a memory from an exchange
curl -s -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"message":"My name is Alice","response":"Nice to meet you Alice!","identity_id":"pluto","user_id":"me"}'

# Get context again — see accumulated memories
curl -s -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -d '{"message":"What do you know about me?","identity_id":"pluto","user_id":"me"}'
```

Or run the full demo: `bash demo.sh`

---

## Verified Capabilities

Each claim below is backed by a repeatable, automated test with a real LLM (no mocks). Run them yourself to verify.

| # | Claim | Proof | How to Run |
|---|-------|-------|------------|
| 1 | **Identity survives provider switch** — memories created with one LLM provider are recalled when the same identity runs on a different provider | `tests/test_portability.py` creates identity with **OpenRouter (gpt-4o)**, shares a personal fact, destroys runtime, loads with **Groq (llama-3.3-70b-versatile)**, asks continuity question — response references the prior fact | `pytest tests/test_portability.py -v --timeout=120` (requires `OPENROUTER_API_KEY` + `GROQ_API_KEY` in `.env`) |
| 2 | **SDK works in 5 lines** — `Identity.create()` → observe facts → set goals → build relationships → export portable JSON, no API key required | SDK Quickstart code block below | `pip install identityos && python` then paste the 5-line example |
| 3 | **Identity survives full restart** — after a multi-turn conversation building personal context, the runtime is destroyed, a fresh runtime loads the same identity from storage, and a continuity question is answered correctly | `tests/test_restart_continuity.py` runs 3-turn conversation (name, trip plan, excitement details) with **Groq (llama-3.3-70b)**, destroys runtime, loads fresh, asks recall question — response references **Alice, Japan, Tokyo food** | `pytest tests/test_restart_continuity.py -v --timeout=180` (requires `GROQ_API_KEY` in `.env`) |
| 4 | **Chrome extension API works** — all endpoints the extension calls (health, list, create, get identity, context, evaluate) are tested end-to-end against a live server | `tests/test_extension_api.py` — starts runtime server, validates all 6 extension endpoints return correct responses | `pytest tests/test_extension_api.py -v --timeout=30` (requires running server or uses module-scoped fixture to start one) |
| 5 | **Full local demo via curl** — create identity, inject context into any chat UI, store memories, verify recall — all from a single `bash demo.sh` script | `demo.sh` runs 7 curl commands against the live runtime server, showing identity creation, context injection, memory storage, and accumulated recall | `bash demo.sh` (requires runtime server on localhost:8000 — run `setsid python -m runtime.main` first) |

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
