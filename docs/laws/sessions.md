# Sessions Law

**Domain:** Sessions
**Constitutional Basis:** Article XI

---

## Purpose

Govern how sessions are created, detected, isolated, and restored. Sessions are the boundary between the identity and interaction.

## Responsibilities

- Create and manage interaction sessions
- Detect session mode from user input
- Isolate non-NORMAL sessions from canonical identity
- Fork FactStore for isolated sessions
- Persist and restore session state
- Clean up session resources on end

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Create session | Yes | On first interaction |
| Detect mode | Yes | From user input |
| Fork FactStore | Yes | For non-NORMAL modes |
| Mutate canonical | NORMAL only | Only in NORMAL sessions |
| Mutate fork | ISOLATED only | Only in non-NORMAL sessions |
| End session | Yes | On request or timeout |

## Conflict Resolution

- Session mode is detected from user input patterns, not pre-assigned
- Detection order: SIMULATION > DREAM > HYPOTHETICAL > ROLEPLAY > NORMAL
- Isolated sessions use a forked FactStore; mutations don't reach canonical
- Session forks persist and are restored when the session is resumed

## Mode Detection Patterns

| Mode | Trigger Pattern |
|------|----------------|
| SIMULATION | "simulate", "simulation", "in a simulation" |
| DREAM | "dream", "in a dream" |
| HYPOTHETICAL | "hypothetical", "what if", "suppose", "imagine that" |
| ROLEPLAY | "let's roleplay", "pretend", "act as" |
| NORMAL | Default (no trigger matched) |

## Evidence Requirements

- Every session records its detected mode
- Session forks record their creation timestamp and source identity version
- Session mode is emitted in session lifecycle events

## Lifecycle

1. **Start** — First interaction on a session_id creates the session
2. **Mode Detection** — User input is analyzed for mode triggers
3. **Forking** — Non-NORMAL sessions fork the canonical FactStore
4. **Interaction** — All mutations go to the appropriate FactStore
5. **Persistence** — Session state is persisted to storage
6. **Restoration** — Same session_id restores the forked state
7. **End** — Session resources cleaned up; forks may persist for later restoration

## Examples

```python
# Auto-detection
mode = detect_session_mode("lets roleplay you are a pirate")
# → SessionMode.ROLEPLAY

# Forking
session_fs = canonical_fs.fork()
# Mutations go to session_fs, not canonical_fs

# Restoration
session_fs = _load_session_fact_store(session_id)
```

## Future Extensions

- Session timeouts and auto-cleanup
- Session sharing across identities
- Session export/import
- Session replay
