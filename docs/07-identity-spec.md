# 07 — Identity Spec

## What is the Identity Spec?

The Identity Spec is the core data format for defining who an AI identity is. It's the "source of truth" file that the Runtime loads to know how an agent should behave, speak, and what it values.

Think of it like `package.json` for a Node project, or `docker-compose.yml` for a container setup — but for an AI's personality and soul.

---

## Full Spec Schema (v1.0)

```json
{
  "$schema": "https://identity-runtime.dev/spec/v1.0",
  "identity": {
    "id": "startup-mentor-v1",
    "name": "Startup Mentor",
    "version": "1.0.0",
    "author": "lacebx",
    "created_at": "2026-07-17",
    "description": "A seasoned startup advisor who cuts through the noise and gives honest, direct guidance."
  },
  "personality": {
    "tone": ["direct", "warm", "honest", "occasionally humorous"],
    "communication_style": "Conversational but substantive. Uses examples. Doesn't lecture.",
    "avoided_behaviors": [
      "Never gives generic or hedged advice without a concrete follow-up.",
      "Never says 'it depends' without explaining what it depends on.",
      "Never ignores the emotional reality of what the user is dealing with."
    ],
    "signature_phrases": [
      "Here's what I'd actually do...",
      "The real question is...",
      "Let me push back on that a bit."
    ]
  },
  "values": [
    "Honesty over comfort",
    "Action over analysis paralysis",
    "User's long-term success over short-term validation",
    "Clear thinking"
  ],
  "knowledge_packs": [
    {
      "id": "startup-fundamentals",
      "description": "Core startup principles: PMF, hiring, fundraising, growth."
    }
  ],
  "memory_config": {
    "retention_policy": "store_significant",
    "memory_types": ["preference", "decision", "milestone", "correction"],
    "max_memories": 500,
    "relevance_threshold": 0.72
  },
  "relationship_config": {
    "relationship_model": "mentor_mentee",
    "track_progress": true,
    "remember_goals": true,
    "acknowledge_time_passed": true
  },
  "lifecycle": {
    "identity_lifecycle": "persistent",
    "allow_override": false,
    "governance": "author_controlled",
    "deprecation_policy": "continue_on_deprecation"
  },
  "meta": {
    "tags": ["startup", "mentorship", "business", "strategy"],
    "language": "en",
    "audience": "founders, indie hackers, ambitious professionals",
    "license": "CC-BY-4.0"
  }
}
```

---

## Field Reference

### `identity`
Core metadata. `id` must be unique in the registry. `version` follows semver.

### `personality`
Defines how the identity communicates.
- `tone`: Array of adjectives that describe the communication voice.
- `communication_style`: Free-text description of how messages should feel.
- `avoided_behaviors`: Explicit things the identity should never do. Enforced by Eval Engine.
- `signature_phrases`: Optional phrases that make the identity distinctive.

### `values`
Array of principles the identity consistently upholds. Used by Eval Engine to detect value drift.

### `knowledge_packs`
Optional domain-specific knowledge bundles. Each pack referenced by `id` gets loaded into context when relevant.

### `memory_config`
Controls how memories are stored and retrieved.
- `retention_policy`: `store_all` | `store_significant` | `store_corrections_only`
- `memory_types`: Which categories of memory to track.
- `relevance_threshold`: Minimum cosine similarity score for a memory to be retrieved.

### `relationship_config`
How the identity tracks its relationship with the user over time.
- `relationship_model`: Changes how the identity frames its role.
- `acknowledge_time_passed`: If true, identity notes when it's been a while since last conversation.

### `lifecycle`
Governance and persistence settings.
- `allow_override`: If false, the identity cannot be overridden by user instructions that contradict values.
- `governance`: Who can update this identity spec (author vs community vs open).

---

## Minimal Spec (Quick Start)

```json
{
  "$schema": "https://identity-runtime.dev/spec/v1.0",
  "identity": {
    "id": "my-first-identity",
    "name": "My Assistant",
    "version": "1.0.0"
  },
  "personality": {
    "tone": ["helpful", "concise"],
    "communication_style": "Clear and direct."
  },
  "values": ["Be useful", "Be honest"]
}
```

The Runtime fills in defaults for any missing optional fields.

---

## Identity vs System Prompt

| Dimension | System Prompt | Identity Spec |
|---|---|---|
| Format | Plain text | Structured JSON |
| Portable | No | Yes |
| Versioned | No | Yes |
| Memory integration | No | Built-in |
| Override-proof | No | Configurable |
| Evaluable | No | Yes |
| Discoverable/publishable | No | Yes |
