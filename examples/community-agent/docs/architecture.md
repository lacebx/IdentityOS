# Community Agent Architecture

## Overview

```
┌─────────────────────────────────────────────────────┐
│                    Discord                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Commands  │  │ Listeners │  │   Scheduler      │   │
│  │ /about    │  │ on_message│  │ reminders()      │   │
│  │ /status   │  │ auto-detect│  │ daily_digest()   │   │
│  │ /evidence │  │ intentions │  │ weekly_digest()  │   │
│  │ /digest   │  │ meetings   │  └──────────────────┘   │
│  │ /reminders│  │ outcomes   │                         │
│  └──────────┘  └──────────┘                            │
└──────────────────────┬──────────────────────────────────┘
                       │ ONLY
                       ▼
┌─────────────────────────────────────────────────────┐
│              IdentityOS SDK                          │
│  ┌──────────────────────────────────────────────┐   │
│  │         IdentityObject                        │   │
│  │  .chat() .intention() .goal() .remember()     │   │
│  │  .observe() .relationship() .timeline()       │   │
│  │  .evidence() .confidence() .export()          │   │
│  │  .infer_intentions() .infer_meetings()        │   │
│  │  .reminders() .team_status() .digest()        │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│            IdentityOS Runtime                        │
│  Goal Engine  │  Intention Engine  │  Memory Store   │
│  Timeline     │  Identity Graph    │  Fact Store     │
│  Evidence Graph│  Confidence Scorer│  User Profile   │
└─────────────────────────────────────────────────────┘
```

## How IdentityOS is Used

The Community Agent treats IdentityOS exactly like a third-party package. The only import is:

```python
from identityos import Identity
```

Every feature — conversation, intention detection, meeting tracking, reminders, summaries, evidence, relationships — goes through a single `IdentityObject` instance.

## How the SDK is Used

- **`identity.chat()`** — All Discord messages are routed through chat(), giving the agent a persistent personality and memory.
- **`identity.infer_intentions()`** — Natural language commitments like "I'll finish authentication tomorrow" are parsed and stored as Intentions with deadlines.
- **`identity.infer_meetings()`** — Meeting proposals like "Let's meet Friday" are detected and recorded as Timeline events.
- **`identity.reminders()`** — The scheduler checks for overdue/expiring intentions and generates human-readable reminders.
- **`identity.team_status()`** — Aggregates active goals, intentions (grouped by author), timeline events, relationships, and meetings.
- **`identity.digest()`** — Generates daily and weekly digests from the identity's complete state.
- **`identity.relationship()`** — Tracks trust levels between the agent and Discord users.
- **`identity.evidence()`** / **`identity.provenance()`** / **`identity.confidence()`** — Provides explainability for every statement.
- **`identity.session()`** — Each Discord channel/thread gets an isolated session.

## How Reminders Work

1. `infer_intentions()` detects commitments and creates Intentions with `expires_at` timestamps
2. `reminders()` queries the runtime for intentions that are overdue, due soon, or approaching
3. The scheduler runs every N minutes and sends Discord messages for overdue items
4. When a user says "I finished" or similar, `complete_authors_intention()` resolves the matching intention

## How Meetings Work

1. `infer_meetings()` detects patterns like "Let's meet Friday at 7" using regex
2. Meeting events are recorded in the timeline and stored as memories
3. Meeting outcomes are recorded via `record_meeting_outcome()` with participants, summary, and decisions
4. Before meetings, the scheduler can check for upcoming meetings (future enhancement)

## How Intentions Work

1. Users make commitments naturally ("I'll deploy tomorrow")
2. `infer_intentions()` pattern-matches and creates an Intention with:
   - Description (the task)
   - Author ID (who committed)
   - Deadline (parsed from temporal expressions)
   - Metadata (source channel, source text)
3. Intentions appear in `/status`, `/reminders`, digests, and team summaries
4. Users can complete intentions by saying "I finished" or using slash commands

## Directory Structure

```
examples/community-agent/
├── main.py                   # Bot entry point
├── config.py                 # Environment configuration
├── .env.example              # Template for secrets
├── requirements.txt          # Dependencies
├── README.md                 # This file
├── commands/                 # Discord slash commands
│   └── __init__.py           # /about, /status, /digest, /evidence, etc.
├── listeners/                # Discord event handlers
│   └── conversation.py       # Message processing pipeline
├── scheduler/                # Background tasks
│   └── __init__.py           # Reminders, daily/weekly digests
├── services/                 # Business logic
│   ├── identity.py           # Load/create identity, about, constitution, evidence
│   ├── conversation.py       # Message processing
│   ├── intentions.py         # Intention management
│   ├── meetings.py           # Meeting tracking
│   └── summary.py            # Team status, digest generation
├── tests/                    # Test suite
│   ├── test_conversation.py
│   ├── test_intentions.py
│   ├── test_meetings.py
│   ├── test_reminders.py
│   ├── test_relationships.py
│   ├── test_timeline.py
│   ├── test_export.py
│   ├── test_isolation.py
│   └── test_simulation.py
└── docs/
    └── architecture.md       # This file
```
