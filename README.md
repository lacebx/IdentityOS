# IdentityOS — identity-runtime

> An operating system for persistent, portable AI identities.

> *Inspired by the anime Pluto — where every robot had its own unique soul.*

---

## Vision

IdentityOS is not a prompt wrapper. It is a **microkernel architecture** for AI entities that persist across sessions, evolve over time, and maintain coherent identity regardless of which client or model they run on.

An identity in this system is not a character definition. It is a **living entity** with:
- A kernel (who it is)
- Memory (what it knows from experience)
- Knowledge (what it was taught)
- Skills (what it can do)
- Goals (what it is trying to accomplish)
- Relationships (who it knows and trusts)
- Policies (what it will and will not do)
- An Evaluation Engine (how it measures itself)

---

## Architecture

```
identity-runtime/
├── core/                    # Bounded modules — the kernel components
│   ├── identity.py          # Identity definition, traits, versioning
│   ├── memory.py            # Memory tiers (episodic, semantic, procedural)
│   ├── knowledge.py         # Knowledge packs with dependency resolution
│   ├── skills.py            # Executable skills and registry
│   ├── relationships.py     # Identity Graph — trust, edges, decay
│   ├── goals.py             # Goal engine with milestones and priority
│   ├── policies.py          # Behavioral policies (allow/deny/transform)
│   ├── evaluation.py        # Evaluation engine with growth tracking
│   └── context_composer.py  # Assembles all modules into a prompt context
├── runtime/
│   └── orchestrator.py      # The microkernel — routes the full pipeline
├── adapters/
│   ├── base.py              # Abstract adapter interface
│   └── openai_adapter.py    # OpenAI, Anthropic, Ollama adapters
├── sdk/
│   └── identity_object.py   # Developer-facing identity interface
├── docs/                    # Architecture docs and specs
├── examples/                # Usage examples
└── extension/               # VSCode extension (thin client)
```

---

## Core Design Principles

| Principle | Description |
|---|---|
| **Identity is the Kernel** | Everything else (Memory, Skills, etc.) is a loadable module |
| **Modularity** | Clean boundaries between modules. No cross-module coupling |
| **Runtime Orchestration** | The Runtime routes interactions. Modules have no orchestration logic |
| **Adapters are Dumb** | Adapters translate and call. No business logic |
| **SDK feels Human** | Interact with identities like individuals, not APIs |
| **Evaluation drives Evolution** | Every interaction is scored. Identity improves over time |

---

## Quick Start

```python
from core.identity import Identity
from runtime.orchestrator import IdentityRuntime
from adapters.openai_adapter import OpenAIAdapter
from sdk.identity_object import load_identity

# 1. Configure adapter
adapter = OpenAIAdapter(model="gpt-4o", api_key="sk-...")

# 2. Boot the runtime
runtime = IdentityRuntime(adapter=adapter)

# 3. Define an identity
mentor = Identity(
    name="Mentor",
    role="Senior Engineer & Advisor",
    persona="Direct, insightful, challenges assumptions",
    core_values=["clarity", "growth", "honesty"],
    communication_style="Concise, structured, Socratic",
)
runtime.register(mentor)

# 4. Interact via SDK
identity = load_identity(runtime, mentor.id)
identity.begin_session()

response = identity.chat("What should I prioritize today?")
print(response)

identity.remember("User is building an IdentityOS project")
identity.pursue("Help user ship Architecture v1.0")
print(identity.describe())
```

---

## Interaction Pipeline

```
User Input
    ↓
[Policy: INPUT]       ← Block/transform harmful inputs
    ↓
[ContextComposer]     ← Assemble identity + memory + knowledge + goals
    ↓
[Adapter]             ← Call LLM (OpenAI / Anthropic / Ollama / ...)
    ↓
[Policy: OUTPUT]      ← Block/transform harmful outputs
    ↓
[EvaluationEngine]    ← Score: consistency, alignment, quality, policy
    ↓
[MemoryStore]         ← Store interaction as episodic memory
    ↓
Response
```

---

## Module Responsibilities

### `core/identity.py`
Defines **who the identity is**. Traits, persona, values, communication style, system prompt. Includes `IdentityVersion` for branching/evolution tracking.

### `core/memory.py`
Three-tier memory: **Episodic** (events), **Semantic** (facts), **Procedural** (how-to). Supports keyword search and recency retrieval.

### `core/knowledge.py`
Knowledge Packs with tier classification (CORE / DOMAIN / CONTEXT / TEMP) and dependency resolution. Identities load packs like modules.

### `core/skills.py`
Executable capabilities. Skills have typed parameters, handlers, and usage tracking. `SkillRegistry` exposes a prompt manifest.

### `core/relationships.py`
The **Identity Graph** — directed edges with type, trust level, strength, and decay. Models the social fabric between identities.

### `core/goals.py`
Goals with priority, scope, milestones, and nested sub-goals. `GoalEngine` provides a top-priority queue and prompt-ready summaries.

### `core/policies.py`
Behavioral guardrails. Policies evaluate data at INPUT, OUTPUT, MEMORY, SKILL, or RELATIONSHIP scope with ALLOW / DENY / TRANSFORM effects.

### `core/evaluation.py`
The **Evaluation Engine** — scores interactions across dimensions (consistency, alignment, quality, policy, growth, empathy). Powers identity evolution.

### `core/context_composer.py`
Assembles all active modules into a single `ComposedContext` for injection into LLM prompts. Token-budget aware.

### `runtime/orchestrator.py`
The **microkernel**. Owns the full interaction pipeline. Orchestrates all modules. Exposes clean `process()` and session management APIs.

### `adapters/`
Thin LLM translation layer. `BaseAdapter` defines the interface. Included: `OpenAIAdapter`, `AnthropicAdapter`, `OllamaAdapter`.

### `sdk/identity_object.py`
The developer-facing API. Interact with identities as individuals: `.chat()`, `.remember()`, `.recall()`, `.pursue()`, `.can()`, `.do()`.

---

## Milestones

| Milestone | Status | Description |
|---|---|---|
| **M1: Architecture v1.0** | ✅ In Progress | Bounded modules with clean interfaces |
| **M2: Persistence Layer** | ⏳ Planned | SQLite/JSON serialization for all stores |
| **M3: Identity Evolution** | ⏳ Planned | Git-style versioning and branching for identities |
| **M4: CLI Client** | ⏳ Planned | `identity run mentor` — thin CLI adapter |
| **M5: VSCode Extension** | ⏳ Planned | Thin client over the runtime |
| **M6: Identity Marketplace** | ⏳ Planned | Shareable identity packs + knowledge packs |

---

## Philosophy

> This is not about better prompts. This is about persistent entities that grow, remember, and relate — across any model, any client, any session.

IdentityOS treats identity as a **first-class primitive** in AI systems. The goal is to make it as natural to work with a persistent AI identity as it is to work with a Git repository: version it, branch it, share it, load it anywhere.

---

*Built by [@lacebx](https://github.com/lacebx)*
