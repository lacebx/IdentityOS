# IdentityOS SDK

**Path:** `sdk/`

The official Python SDK for IdentityOS. Hide all internal runtime complexity behind a clean, typed, well-documented API.

```python
from sdk import Identity

# Load a persisted identity
lace = Identity.load("lace")

# Chat
reply = lace.chat("Hello! How are you?")

# Observe facts
lace.observe("My favorite color is blue")

# Goals
lace.goal("Learn Python", priority="high")

# Intentions
lace.intention("Ask about weekend plans")

# Relationships
lace.relationship("user-123", trust_level=0.8)

# Timeline
events = lace.timeline(limit=10)

# Evidence & confidence
lace.evidence("preferences.favorite_color")
lace.confidence("preferences.favorite_color")

# Constitution
lace.constitution()

# Export
lace.export("lace-portable.json")

# Import
restored = Identity.from_file("lace-portable.json")
```

---

## Getting Started

### Load an existing identity

```python
from sdk import Identity

mentor = Identity.load("mentor-01")
response = mentor.chat("What is your purpose?")
print(response)
```

### Create a new identity

```python
from sdk import Identity

lace = Identity.create(
    name="Lace",
    persona="mentor",
    role="guide",
)
response = lace.chat("Hello!")
print(response)
```

### Import from a portable JSON file

```python
from sdk import Identity

lace = Identity.from_file("lace-portable.json")
```

---

## Full API Reference

### Identity (class methods)

| Method | Description |
|--------|-------------|
| `Identity.load(id, storage_path)` | Load an identity from persistent storage |
| `Identity.create(name, ...)` | Create a new identity |
| `Identity.from_file(path)` | Import from a portable JSON file |

### IdentityObject (instance methods)

#### Chat

| Method | Description |
|--------|-------------|
| `chat(message)` | Send a message and get a response |
| `ask(question)` | Ask a question (alias for chat) |
| `instruct(instruction)` | Give an instruction (alias for chat) |

#### Observe

| Method | Description |
|--------|-------------|
| `observe(text)` | Extract facts from text and store as user knowledge |

#### Memory

| Method | Description |
|--------|-------------|
| `remember(content, tags, memory_type)` | Store a memory |
| `recall(query, limit)` | Retrieve relevant memories |
| `forget(memory_id)` | Remove a specific memory |
| `memories(memory_type, limit)` | List all memories |

#### Goals

| Method | Description |
|--------|-------------|
| `goal(title, description, priority, scope, success_criteria)` | Create a goal |
| `goals(status)` | List goals, filtered by status |
| `complete_goal(goal_id)` | Mark a goal as completed |
| `abandon_goal(goal_id)` | Abandon a goal |

#### Intentions

| Method | Description |
|--------|-------------|
| `intention(description, priority, hours)` | Create a short-term commitment |
| `intentions(status)` | List intentions, filtered by status |
| `complete_intention(intention_id)` | Mark an intention as completed |
| `promote_intention(intention_id, goal_id)` | Promote an intention to a goal |

#### Relationships

| Method | Description |
|--------|-------------|
| `relationship(entity_id, trust_level, context, edge_type)` | Get or set a relationship |
| `relationships()` | List all relationships |

#### Timeline

| Method | Description |
|--------|-------------|
| `timeline(limit)` | Get timeline events |
| `record_event(event_type, title, description, significance)` | Record a custom event |

#### Evidence & Confidence

| Method | Description |
|--------|-------------|
| `evidence(entity_id)` | Get evidence chain for any entity |
| `provenance(entity_id)` | Get full provenance with confidence |
| `confidence(entity_id)` | Get confidence score and details |

#### Constitution

| Method | Description |
|--------|-------------|
| `constitution()` | Load the IdentityOS Constitution and Laws |

#### Sessions

| Method | Description |
|--------|-------------|
| `session()` | Session context manager (for isolated conversations) |
| `sessions()` | List active sessions |

#### Export / Import

| Method | Description |
|--------|-------------|
| `export(path)` | Export identity as portable JSON |
| `import_(data)` | Import data from a portable dict |

#### Skills

| Method | Description |
|--------|-------------|
| `can(skill_name)` | Check if a skill is available |
| `do(skill_name, **kwargs)` | Invoke a skill |
| `skills()` | List all registered skills |

#### Introspection

| Method | Description |
|--------|-------------|
| `describe()` | Detailed snapshot of identity state |
| `user_facts()` | List known user facts |
| `id` (property) | Identity ID |
| `name` (property) | Identity name |
| `persona` (property) | Identity persona |
| `role` (property) | Identity role |
| `version` (property) | Identity version string |

---

## Examples

### 20-line Discord Bot

```python
from sdk import Identity

bot = Identity.load("discord-bot")

@bot.event
async def on_message(message):
    reply = bot.chat(message.content)
    await message.channel.send(reply)
```

### 30-line NPC

```python
from sdk import Identity

npc = Identity.load("village-elder")

def on_player_speak(player_input: str) -> str:
    npc.observe(player_input)
    return npc.chat(player_input)
```

### 40-line Research Assistant

```python
from sdk import Identity

assistant = Identity.load("research-assistant")
assistant.goal("Track papers about transformer architectures")

def process_paper(abstract: str):
    assistant.remember(abstract, tags=["paper", "transformers"])
    summary = assistant.chat(f"Summarize this paper: {abstract}")
    return summary
```

---

## Design Principles

1. **Zero engine knowledge required** — Developers do not need to understand stores, engines, or configs
2. **Everything is optional** — Chat works without goals; goals work without relationships
3. **Minimal imports** — `from sdk import Identity` is all you need
4. **Typed returns** — All methods return dicts with consistent field names
5. **Portable** — Export produces a standalone JSON file that can be shared, migrated, or imported
