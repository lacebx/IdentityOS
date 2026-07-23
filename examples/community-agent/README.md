# IdentityOS Community Agent

A Discord bot powered entirely by the IdentityOS SDK — the first reference application for the IdentityOS platform.

> **No internal modules are imported.** The only IdentityOS import is `from identityos import Identity`.

## Features

### 🧠 Persistent Identity
The bot loads a persistent IdentityOS identity (`community-agent`) that remembers everything across restarts. Every conversation, intention, meeting, relationship, and decision is stored and recallable.

### 💬 Natural Conversations
All Discord messages go through `identity.chat()`. The agent has a consistent personality (persona: `community_manager`, role: `facilitator`) and maintains context through IdentityOS sessions.

### 📋 Automatic Intention Detection
When someone says "I'll finish authentication tomorrow" or "I will deploy tonight", the bot automatically:
- Creates an intention with a deadline
- Tags it with the author
- Records it in the timeline
- Follows up if the deadline passes

### 📅 Meeting Detection
Patterns like "Let's meet Friday at 7" or "We should sync tomorrow" are automatically detected and recorded as timeline events with proposed times.

### ⏰ Intelligent Reminders
If a deadline passes, the bot politely reminds the person. When someone says "I finished", the bot marks the intention complete and updates the timeline.

### 📊 Team Status
Ask "What is everyone working on?" and the bot generates a structured summary from:
- Active goals
- Active intentions (grouped by author)
- Upcoming meetings
- Recent timeline events
- Relationship data

### 🔍 Explainable Everything
Every statement is backed by evidence. Ask "Why do you think that?" and the bot shows confidence scores, provenance, and evidence chains using SDK methods.

### 📝 Daily & Weekly Digests
Automatically generated summaries of completed work, open intentions, upcoming meetings, and timeline highlights.

### 🔒 Session Isolation
Each Discord channel or thread gets its own IdentityOS session, keeping conversations organized.

## Architecture

```
Discord Message → Listener → Services → SDK → IdentityOS Runtime
                                     ↕
                               IdentityObject
                              (single instance)
```

The entire application is a thin layer over one `IdentityObject`. All business logic uses only SDK methods.

## Quick Start

### Prerequisites
- Python 3.10+
- A Discord Bot Token
- IdentityOS (installed from repo root)

### Setup

1. **Clone and install IdentityOS**
   ```bash
   git clone https://github.com/lacebx/IdentityOS.git
   cd IdentityOS
   pip install -e .
   ```

2. **Configure the bot**
   ```bash
   cd examples/community-agent
   cp .env.example .env
   # Edit .env with your Discord token and guild ID
   ```

3. **Run the bot**
   ```bash
   python main.py
   ```

### Discord Commands

| Command | Description |
|---------|-------------|
| `/about` | Show identity information |
| `/status` | Show team status summary |
| `/digest daily` | Generate a daily digest |
| `/digest weekly` | Generate a weekly digest |
| `/evidence <entity_id>` | Show evidence for an entity |
| `/constitution` | Show the IdentityOS Constitution |
| `/reminders` | Show pending reminders |

### Example Conversations

**User:**
> I'll finish authentication tomorrow.

**Bot:**
> Got it! I've tracked that. (Tracked: finish authentication)

---

**User (next day):**
> I finished.

**Bot:**
> Great work! I've marked it as completed.

---

**User:**
> Let's meet Friday at 7.

**Bot:**
> Meeting recorded for Friday.

---

**User:**
> What is everyone working on?

**Bot:**
> ## Team Status
>
> **Alice:** finish authentication (due: tomorrow)
> **Bob:** deploy API (due: Friday)
> ...
> ---

**User:**
> Why do you think that?

**Bot:**
> *Evidence-backed response:*
> Confidence: HIGH (85%)
> Evidence: Alice said "I'll finish authentication" in #general
> ...

## Acceptance Criteria

The following scenarios are verified by the test suite:

1. ✅ "I'll finish authentication tomorrow" → intention created with deadline
2. ✅ 24h later → reminder sent
3. ✅ "I finished" → intention completed, timeline updated, evidence recorded
4. ✅ "Let's meet Friday at 7" → meeting recorded
5. ✅ Post-meeting → participants, summary, decisions recorded
6. ✅ "What are we behind on?" → reasoned from goals/intentions/timeline/evidence
7. ✅ "Why?" → evidence shown
8. ✅ Restart → everything persists
9. ✅ No internal imports
10. ✅ Survives 100+ conversations without crashing

## Testing

```bash
# Run all IdentityOS tests
cd /path/to/identity-runtime
python -m pytest tests/ -q

# Run all SDK tests
python -m pytest tests/ -q -k "sdk"

# Run Community Agent tests
python -m pytest examples/community-agent/tests/ -q

# Run end-to-end simulation
python -m pytest examples/community-agent/tests/test_simulation.py -v
```

## How It Validates the SDK

Before this application, the IdentityOS SDK had:
- Core chat, goals, intentions, memory, relationships, timeline
- Evidence, provenance, confidence
- Export/import

The Community Agent exposed these gaps, which were filled by adding to the SDK (not bypassing it):
- `infer_intentions()` — NLU for commitments
- `infer_meetings()` — NLU for meeting proposals
- `reminders()` — deadline-aware querying
- `team_status()` — aggregated status
- `digest()` — period-based summaries
- `metadata` support in intentions

The result: a real production application built entirely on `from identityos import Identity`.

## Future Roadmap

- [ ] LLM-powered intention detection (complement regex with NLU)
- [ ] Voice channel support
- [ ] Thread-based meeting transcripts
- [ ] GitHub/Linear integration via skills
- [ ] Web dashboard
- [ ] Multi-identity support
