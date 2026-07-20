# IdentityOS — Identity Evolution Engine

The Identity Evolution Engine transforms IdentityOS from a conversation recorder
into an active identity engine that infers, validates, mutates, and preserves
identity state over time.

## Architecture

```
Conversation → Inference → Identity Mutation → Memory → Timeline → Persistence
```

New pipeline stage (inserted between Memory and Timeline in the orchestrator):

```
  7a. Episodic Memory
  7b. Semantic Memory
→ 7c. Identity Mutation (NEW) ←
  8.  Timeline
  9.  Relationships
  10. Persist Goals
```

## Modules

### `core/identity_mutation.py` — The Mutation Engine

Detects identity evolution opportunities from assistant responses:

| Pattern | Example | Field | Type |
|---------|---------|-------|------|
| `I (like/love/prefer) X` | "I like blue" | `preferences.favorite_color` | preference_adopted |
| `I think X fits me` | "I think blue fits me" | `preferences.favorite_color` | preference_adopted |
| `My favorite X is Y` | "My favorite color is red" | `preferences.favorite_color` | preference_adopted |
| `I no longer enjoy X` | "I don't like coffee anymore" | `preferences.drink.coffee` | preference_changed |
| `I (believe/think) X` | "I believe growth is key" | `beliefs.growth_is_key` | belief_adopted |
| `I have become more X` | "I have become more patient" | `traits.patience` | trait_evolved |
| `I trust X` | "I trust you" | `relationships.trust.you` | trust_evolved |

Each detection returns a `MutationProposal`:
```python
{
    "mutation_id": "uuid",
    "mutation_type": "preference_adopted",
    "field": "preferences.favorite_color",
    "old_value": None,
    "new_value": "blue",
    "confidence": 0.88,
    "reason": "Assistant indicated a preference.",
    "source_text": "I think blue fits me.",
    "status": "proposed"
}
```

### IdentitySpec — New Fields

Added to `core/identity.py`:
- `preferences: Dict[str, Any]` — evolved likes/dislikes (e.g., `favorite_color`)
- `beliefs: Dict[str, Any]` — stated beliefs/opinions
- `likes: List[str]` — explicitly liked things
- `dislikes: List[str]` — explicitly disliked things
- `habits: List[str]` — noted habits
- `communication_tendencies: Dict[str, Any]` — communication style evolution
- `mutation_history: List[Dict]` — full audit trail of all mutations

All fields serialize/deserialize through `to_dict()` / `from_dict()` and survive
restart.

### Validation & Contradiction Detection

Before applying mutations, the engine checks:
1. **Confidence threshold** — proposals below 0.5 are rejected
2. **Contradictions** — if a field already has a different value from a prior
   accepted mutation, the proposal is flagged as `CONFLICT` with a reference
   to the conflicting mutation

### ContextComposer — Identity Before Memory

The `ComposedContext` now has an `identity_evolution_block` rendered **before**
the memory block. This ensures the LLM sees evolved identity state first:

```
## Identity: Evolver
Persona: An identity designed to evolve through conversation

## Identity (Evolved)
Preferences:
  - favorite_color: blue

## Relevant Memory
[EPISODIC] User: ...
```

### Timeline — Meaningful Events

New `LifeEventType` values:
- `preference_learned` — when a preference is adopted/changed
- `belief_adopted` — when a belief is adopted
- `trait_changed` — when a trait evolves
- `trust_changed` — when trust in someone changes
- `communication_changed` — when communication style changes
- `contradiction_resolved` — when a contradiction is detected

### Playground — Identity Evolution Panel

The Playground shows:
- **Preferences** (evolved): collapsible section with key-value pairs
- **Beliefs**: collapsible section with stated beliefs
- **Traits**: score bars for each trait
- **Likes/Dislikes**: aggregated lists
- **Mutation History**: full audit trail showing old→new values, status
  (accepted/conflict/rejected), confidence, and reasoning

## Running the Manual Test

```bash
python test_identity_evolution.py
```

This validates:
1. Preference detection from "I think blue fits me"
2. Structured mutation proposals
3. Acceptance and application to identity spec
4. Context rendering with evolved identity before memory
5. Contradiction detection on conflicting preferences
6. Persistence across runtime restart
7. Meaningful timeline events
8. Audit trail explainability

## The Key Demo

```
User:  "You should have your own favorite color."
Assistant:  "I think blue fits me."
          ↓
[Runtime detects mutation: preferences.favorite_color = blue]
[Runtime validates: no contradiction, confidence OK]
[Runtime applies: identity.preferences.favorite_color = "blue"]
[Runtime records: mutation_history, timeline event]
[Runtime persists: identity spec to storage]

User:  "What is your favorite color?"
          ↓
[ContextComposer injects: Identity (Evolved) → favorite_color: blue]
Assistant:  "My favorite color is blue."
          ↑
This answer comes from runtime state, NOT from LLM memory.
```

This is the moment IdentityOS demonstrates behavior that comes from the runtime,
not from an LLM's context window.
