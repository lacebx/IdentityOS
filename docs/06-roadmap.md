# 06 — Roadmap

## Development Phases

---

### Milestone 1: Identity Runtime Core
**Goal**: Working backend that loads an identity, stores memories, and returns augmented context.

**Deliverables**:
- [ ] Identity spec loader (reads JSON spec from file)
- [ ] Memory store (SQLite + local embeddings via Ollama)
- [ ] `/context` API endpoint
- [ ] `/evaluate` API endpoint
- [ ] Basic identity consistency checking
- [ ] Unit tests for core memory retrieval

**Done when**: A `curl` command with a message returns a context-enriched response that includes identity info and relevant past memories.

---

### Milestone 2: Identity Spec v1
**Goal**: A formalized, validated, versioned identity spec format. The "Docker Compose" for who an AI agent is.

**Deliverables**:
- [ ] JSON Schema definition for Identity Spec
- [ ] Spec validator CLI tool
- [ ] 3 example identity specs (Startup Mentor, Personal Assistant, Language Tutor)
- [ ] Identity versioning (identity v1.0, v1.1, etc.)
- [ ] Spec changelog format
- [ ] Documentation: "How to write an identity spec"

**Done when**: An identity spec file passes schema validation and loads correctly into the Runtime.

---

### Milestone 3: Developer SDK Alpha
**Goal**: A simple npm package that developers can use to add persistent identity to any app.

**Deliverables**:
- [ ] `identity-runtime` npm package
- [ ] `IdentityRuntime` class with `retrieve()`, `remember()`, `evaluate()` methods
- [ ] Model adapters: OpenAI, Anthropic, Groq
- [ ] README with quickstart guide
- [ ] Example app (Node.js)
- [ ] Published to npm (alpha)

**Done when**: A developer can add 5 lines of code to any Node.js app to give their chatbot persistent identity.

---

### Milestone 4: Chrome Extension (Bridge) MVP
**Goal**: Extension that makes ChatGPT and Grok feel like they share the same identity layer.

**Deliverables**:
- [ ] Manifest V3 Chrome extension
- [ ] Content scripts for chatgpt.com and grok.com
- [ ] Message interception (outbound + inbound)
- [ ] Popup UI: select active identity, view memory count
- [ ] Identity context injection (invisible prepend)
- [ ] Memory capture on response
- [ ] Working demo: same identity across ChatGPT + Grok
- [ ] Published to Chrome Web Store (beta)

**Done when**: The demo script in `05-mvp.md` works end-to-end.

---

### Milestone 5: Identity Registry
**Goal**: Public registry where developers and creators can publish and discover identity specs.

**Deliverables**:
- [ ] Registry web app (list + search identities)
- [ ] `identity publish` CLI command
- [ ] `identity install <name>` CLI command
- [ ] Identity versioning in registry
- [ ] User accounts (basic auth)
- [ ] Identity page: name, description, author, version history

**Done when**: `npx identity install startup-mentor` installs a published identity spec into the local Runtime.

---

### Milestone 6: Identity Marketplace
**Goal**: Creators can monetize identities. Users/orgs subscribe to premium identities.

**Deliverables**:
- [ ] Paid identity listings
- [ ] Subscription management (Stripe)
- [ ] Creator dashboard (earnings, subscriber count)
- [ ] Identity certification (verified creator badge)
- [ ] Enterprise licensing model
- [ ] Org-level identity management

**Done when**: A creator earns their first $1 from a published identity.

---

## Timeline Estimate

| Milestone | Estimated Duration |
|---|---|
| M1: Runtime Core | 2-3 weeks |
| M2: Identity Spec v1 | 1-2 weeks |
| M3: SDK Alpha | 2-3 weeks |
| M4: Extension MVP | 3-4 weeks |
| M5: Registry | 4-6 weeks |
| M6: Marketplace | 6-8 weeks |

**Total MVP-to-Marketplace estimate: ~5-6 months**

---

## What We're NOT Roadmapping (Yet)

- Mobile app
- Voice interface
- IoT / robotics integration
- Studio (creator tooling)
- Governance / identity lifecycle standards

These are post-traction features.
