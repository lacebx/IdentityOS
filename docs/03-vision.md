# 03 — Vision

## The Full Ecosystem

identity-runtime is not just a library. It is an ecosystem — a platform for creating, owning, sharing, and deploying persistent AI identities.

---

## The Five Layers

### Layer 1: Identity Runtime (Core)
The engine. Handles:
- Memory storage and retrieval
- Identity spec loading and enforcement
- Context assembly before LLM calls
- Memory evaluation after LLM responses
- Identity consistency tracking

### Layer 2: Identity Spec
The standard. A structured format (JSON/YAML) that defines who an AI identity is:
- Personality traits and tone
- Core values and ethical guidelines
- Long-term goals and preferences
- Relationship history and context
- Knowledge packs (specialized domains)

### Layer 3: Extension (Bridge Client)
The first user-facing product. A Chrome extension that:
- Intercepts user messages on ChatGPT, Grok, etc.
- Prepends relevant memory and identity context before messages are sent
- Captures responses and evaluates what's worth remembering
- Keeps the familiar UI — invisible to the user

### Layer 4: SDK
For developers. A simple package that:
- Loads an identity spec from file or registry
- Exposes `retrieve`, `remember`, `evaluate` APIs
- Works with any LLM API (OpenAI, Anthropic, Groq, etc.)
- Makes it trivial to add persistent identity to any app

### Layer 5: Registry & Marketplace
For the ecosystem.
- **Registry**: Publish identity specs publicly (like npm packages)
- **Marketplace**: Creators monetize identities. Users/orgs subscribe.
- **Studio**: Creator tools to build, test, version, and certify identities

---

## Identity Composition (The Lego Model)

An identity is not a monolith. It's a composition:

```
Identity = Base Personality
         + Knowledge Pack(s)
         + Memory Store
         + Model Adapter
```

Example: "AP Calculus Tutor"
- Base Personality: patient, encouraging, analytical
- Knowledge Pack: AP Calculus curriculum + common misconceptions
- Memory Store: this student's progress, past errors, mastered topics
- Model Adapter: Claude 3 Sonnet (or swap to GPT-4o)

This modularity means:
- Identities evolve naturally instead of being hard-coded
- Knowledge packs can be updated without changing the personality
- Different models can run the same identity

---

## The Ecosystem Flywheel

```
Creators build identities
        ↓
Developers integrate via SDK
        ↓
Users subscribe + interact
        ↓
Memories accumulate (owned by user)
        ↓
Identity becomes more valuable over time
        ↓
Creators get paid. Platform grows.
```

---

## Long-Term Horizon

The browser extension is just the first client. Future interfaces include:
- IDE plugins (Cursor, VS Code)
- Mobile apps
- Voice assistants
- IoT / smart home devices
- Eventually: actual robots and humanoid devices

When physical AI becomes mainstream, the identity layer becomes the soul that travels across devices — the same way your iCloud identity follows you across Apple hardware.

---

## What Makes This Different From Character.AI or Similar

| Feature | Character.AI | identity-runtime |
|---|---|---|
| Identity ownership | Platform owns it | User/creator owns it |
| Model flexibility | Locked to their model | Works with any model |
| Developer access | No SDK | Full SDK + spec |
| Portability | Zero | Core feature |
| Memory ownership | Platform | User |
| Monetization | Platform takes cut | Creator-first marketplace |
