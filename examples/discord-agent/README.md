# IdentityOS Discord Agent

A production-ready Discord bot powered by **IdentityOS**.

> Uses ONLY `from identityos import Identity` — zero internal runtime imports.

## Quick Start (5 minutes)

### 1. Create a Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application**, name it (e.g. "My Agent")
3. Go to **Bot** → **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ MESSAGE CONTENT INTENT
   - ✅ SERVER MEMBERS INTENT
5. Copy the **Token**

### 2. Invite the Bot

1. Go to **OAuth2** → **URL Generator**
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select permissions:
   - ✅ Send Messages
   - ✅ Read Message History
   - ✅ Use Slash Commands
4. Open the generated URL, select your server

### 3. Configure

```bash
cd examples/discord-agent
cp .env.example .env
# Edit .env — paste your DISCORD_TOKEN and GUILD_ID
```

### 4. Run

**Locally:**
```bash
make run
```

**With Docker:**
```bash
make docker-build && make docker-up
```

## Commands

| Command | Description |
|---|---|
| `/about` | Identity information, version, stats |
| `/status` | Team status: goals, intentions, reminders |
| `/goals` | List active goals |
| `/intentions` | List active intentions (by author, with deadlines) |
| `/reminders` | Show pending/overdue reminders |
| `/digest daily\|weekly` | Generate activity digest |
| `/timeline` | Recent timeline events |
| `/evidence <id>` | Evidence chain for an entity |
| `/confidence <id>` | Confidence score for an entity |
| `/constitution` | IdentityOS Constitution & Laws |
| `/help` | This command list |

## Automatic Detection

The bot automatically detects these patterns in conversation:

- **Commitments:** "I'll finish authentication tomorrow." → intention with deadline
- **Meetings:** "Let's meet Friday at 7." → timeline event
- **Completion:** "I finished." → intention marked complete
- **Evidence requests:** "Why do you think that?" → evidence chain

## Architecture

```
Discord Message
  → listeners/  (event handlers)
    → pipeline/  (message processing pipeline)
      → services/  (business logic)
        → identityos  (PUBLIC SDK ONLY)
          → IdentityOS Runtime (internal)
```

The application never imports `runtime/`, `core/`, or any internal package.

## Deployment

### Directory Structure

```
examples/discord-agent/
├── main.py                    # Bot entry point
├── config.py                  # Env-based config with validation
├── commands/                  # 11 slash commands
├── listeners/                 # Discord event handlers
├── pipeline/                  # Message processing pipeline
├── scheduler/                 # Reminders + digests
├── services/                  # Business logic
├── tests/                     # Test suite
├── Dockerfile                 # Container build
├── docker-compose.yml         # Multi-service setup
├── Makefile                   # Dev commands
└── .env.example               # Configuration template
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | — | Discord bot token (required) |
| `GUILD_ID` | — | Discord server ID (required) |
| `IDENTITY_ID` | `discord-agent` | IdentityOS identity ID |
| `IDENTITY_NAME` | `Discord Agent` | Display name |
| `IDENTITY_CLASS` | `assistant` | Identity class |
| `IDENTITY_STORAGE_PATH` | `/data/identities` | Where identities persist |
| `REMINDER_INTERVAL_MINUTES` | `30` | How often to check reminders |
| `DIGEST_TIME_DAILY` | `09:00` | Daily digest time (HH:MM) |
| `DIGEST_TIME_WEEKLY` | `09:00` | Weekly digest time (HH:MM) |
| `DIGEST_DAY_WEEKLY` | `monday` | Weekly digest day |
| `TIMEZONE` | `UTC` | Timezone for scheduling |
| `LOG_LEVEL` | `INFO` | Logging level |
| `HEALTHCHECK_PORT` | `8080` | Healthcheck HTTP port |
| `COMMAND_SYNC_ON_START` | `true` | Sync slash commands on startup |

### Persistence

Identities are stored at `IDENTITY_STORAGE_PATH` (default: `/data/identities`).
In Docker, this is a named volume `identityos-data`.

To back up an identity:
```bash
make inspect ID=discord-agent
docker compose exec discord-agent python3 -c "
from identityos import Identity
i = Identity.load('discord-agent')
i.export('/data/identities/backup.json')
"
```

To restore:
```bash
docker compose exec discord-agent python3 -c "
from identityos import Identity
i = Identity.from_file('/data/identities/backup.json')
"
```

### Healthcheck

The bot exposes an HTTP healthcheck on port `8080`:
```
GET /healthz → {"status":"healthy"}
```

## Testing

```bash
# Run all IdentityOS tests
cd /path/to/identity-runtime
python -m pytest tests/ -q

# Run Discord agent tests
cd examples/discord-agent
make test

# Run end-to-end scenarios
python -m pytest tests/test_scenarios.py -v
```

## Verification

All 10 acceptance criteria are verified:
1. ✅ "I'll finish authentication tomorrow." → intention + deadline
2. ✅ "I finished." → complete + timeline + evidence
3. ✅ "Let's meet Friday at 7." → meeting recorded
4. ✅ Preference learning → fact stored
5. ✅ Preference updates → contradictions tracked
6. ✅ Relationships → trust graph updated
7. ✅ Reminders → overdue tracking
8. ✅ Team status → aggregated from goals/intentions/events
9. ✅ Evidence → confidence + provenance
10. ✅ Restart → full persistence

## SDK Usage

```python
from identityos import Identity

# Load existing
agent = Identity.load("discord-agent")

# Or create new
agent = Identity.create(
    name="My Agent",
    identity_class="assistant",
)

# Chat
reply = agent.chat("Hello!")
print(reply)

# Goals
agent.goal("Ship v2", priority="high")

# Intentions
agent.intention("Review PR", hours=24)

# Evidence
print(agent.evidence(entity_id))
print(agent.confidence(entity_id))

# Persistence
agent.export("backup.json")
```
