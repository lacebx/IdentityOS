# 04 — Architecture

## System Overview

```
┌────────────────────────────────────────────────┐
│               CLIENT LAYER                    │
│  Chrome Extension  |  SDK  |  Web App  |  API  │
└────────────────────────────────────────────────┘
                         │
┌────────────────────────────────────────────────┐
│           IDENTITY RUNTIME SERVICE              │
│                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Context Builder  │  │  Memory Engine   │  │
│  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Identity Loader   │  │ Eval Engine     │  │
│  └─────────────────┘  └─────────────────┘  │
└────────────────────────────────────────────────┘
                         │
┌────────────────────────────────────────────────┐
│           MODEL ADAPTERS                        │
│  GPT Adapter | Claude Adapter | Grok Adapter   │
└────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Context Builder
Assembles the full context before a message is sent to the model:
- Pulls identity spec (personality, values, tone)
- Retrieves relevant memories (semantic search on past interactions)
- Applies context layering: `[user preferences] + [identity context] + [relevant memories] + [current message]`

### 2. Memory Engine
Manages the persistent store of interactions and learned facts:
- Stores: episodic memories (what happened), semantic memories (what was learned), preference memories (what the user likes/wants)
- Retrieval: semantic search to find relevant memories for current context
- Pruning: removes stale or low-relevance memories over time

### 3. Identity Loader
Loads and validates identity specs:
- Reads from local file, registry URL, or inline JSON
- Validates against the Identity Spec schema
- Makes identity available to Context Builder

### 4. Eval Engine
Evaluates responses and decides what to remember:
- Did this interaction reveal a new preference?
- Did the user correct the identity's behavior?
- Is the identity drifting from its spec?
- What memory should be stored for future retrieval?

### 5. Model Adapters
Adapter pattern: one small interface per model provider:
```typescript
interface ModelAdapter {
  sendMessage(context: IdentityContext, message: string): Promise<string>
  getModelName(): string
}
```
Each adapter (GPT, Claude, Grok) implements this same interface. The Runtime doesn't care which model is underneath.

---

## Message Flow (Extension MVP)

```
1. User types into ChatGPT input box
2. Extension content script intercepts the message (before send)
3. Extension calls Runtime API: POST /context {message, identity_id, user_id}
4. Runtime:
   a. Loads identity spec
   b. Retrieves relevant memories (top-k semantic search)
   c. Assembles context: [identity] + [memories] + [original message]
   d. Returns assembled context
5. Extension prepends context to user message (invisible to user)
6. Augmented message sent to ChatGPT
7. ChatGPT responds
8. Extension captures response
9. Extension calls Runtime API: POST /evaluate {message, response}
10. Runtime eval engine decides what to store
11. New memory stored if warranted
```

---

## Data Storage

### Identity Store
- JSON/YAML files (local) or database rows (hosted)
- Versioned (identity v1, v2, etc.)
- Referenced by stable `identity_id`

### Memory Store
- Vector database for semantic retrieval (pgvector, Pinecone, or local FAISS)
- Each memory: `{content, embedding, timestamp, relevance_score, memory_type}`
- Partitioned per `(user_id, identity_id)`

### User Session Store
- Active identity per user
- Session preferences (overrides)
- Interaction counts / relationship metadata

---

## Design Principles

1. **The Runtime owns the identity layer.** The model is replaceable; the Runtime is not.
2. **Context layering, not overriding.** We compose context on top of whatever the model already has. We don't fight with existing system prompts.
3. **Adapters, not integrations.** Each model provider gets a thin adapter. The core Runtime has no model-specific code.
4. **Eval is first-class.** Identity consistency measurement is built in from day one. Not an afterthought.
5. **Portable by design.** Every data structure is designed to be exportable, importable, and model-agnostic.
