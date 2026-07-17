# identity-runtime

> The infrastructure for persistent AI identities that work across models and eventually devices.
> *Inspired by the anime Pluto — where every robot had its own unique AI soul.*

---

## What is this?

Today, AI models like ChatGPT, Claude, and Grok are powerful but stateless. Every conversation starts fresh. Every model has a different "personality." Users are locked into one provider's memory system. Developers can't build consistent AI agents that persist across tools.

**identity-runtime** is the missing layer: a portable identity and memory engine that sits between users/developers and any LLM. Think of it as the operating system for AI personalities.

---

## The North Star

> **Identity portability across models — so developers and users are never locked into one provider.**

Just like Docker made apps portable across servers, identity-runtime makes AI identities portable across reasoning engines.

---

## Repository Structure

```
identity-runtime/
├── README.md                  # This file
├── docs/
│   ├── 01-north-star.md       # The guiding vision
│   ├── 02-problem.md          # Problem statement
│   ├── 03-vision.md           # Full vision & ecosystem
│   ├── 04-architecture.md     # Technical architecture
│   ├── 05-mvp.md              # MVP scope & plan
│   ├── 06-roadmap.md          # Development roadmap
│   └── 07-identity-spec.md    # Identity spec format
├── extension/                 # Chrome extension (MVP client)
├── runtime/                   # Core identity runtime service
├── sdk/                       # Developer SDK
└── registry/                  # Identity registry / marketplace
```

---

## Quick Concept

```
User types message
       ↓
Extension intercepts
       ↓
Runtime pulls relevant memories + identity context
       ↓
Context prepended to prompt
       ↓
Sent to ChatGPT / Claude / Grok
       ↓
Response returned
       ↓
Runtime evaluates what's worth remembering
       ↓
Memory store updated
```

The user sees the familiar ChatGPT/Grok interface. Underneath, the identity layer is shaping every conversation.

---

## Ecosystem Vision

| Layer | Description |
|---|---|
| **Identity Runtime** | Core engine: memory, identity spec, evaluation |
| **Extension (Bridge)** | Chrome extension — first client, injects context into existing AI UIs |
| **SDK** | For developers to load identities into their own apps |
| **Registry / Marketplace** | Where creators publish identities, others subscribe |
| **Studio** | Creator tools: build, test, version identities |

---

## Key Principles

1. **We own the identity layer, not the model.** Models are CPU. We are the OS.
2. **Don't compete with ChatGPT.** Be the layer that makes ChatGPT better for every user.
3. **Identity = personality + memory + values + history.** Not just a system prompt.
4. **Modular.** Identity + knowledge pack + memory + model. Mix like Lego pieces.
5. **Portable.** Same identity, different model — continuity is the product.

---

## Milestones

- **M1** — Identity Runtime Core (web app demo: one identity, two models)
- **M2** — Identity Spec v1 (JSON schema, like Docker Compose for who the agent is)
- **M3** — Developer SDK alpha
- **M4** — Chrome Extension MVP (Bridge client for ChatGPT/Grok)
- **M5** — Identity Registry (public identity publishing)
- **M6** — Identity Marketplace (monetization, subscriptions)

See [`docs/06-roadmap.md`](docs/06-roadmap.md) for full details.

---

## Status

> Pre-MVP. Concept validated. Building starts now.

---

## Inspiration

Watching *Pluto* (2023 Netflix anime) raised a question: in the show, each robot has its own AI — Officer Gesicht's AI is distinct from Atom's, Hercules', or Brando's. They reference each other as individuals, not as instances of the same model.

In our world, we have ChatGPT, Claude, Grok — one big model each. But when you build chatbots or agents, you give them a system prompt and call it a personality. Is that real individuality? Or just a costume over the same base model?

This project explores what it would take to make AI identities *real* — persistent, portable, and owned.
