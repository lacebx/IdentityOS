# Identity Debugger and Replay

IdentityOS persists one diagnostic record for every completed interaction. The
record contains runtime-observed pipeline stages, policies, context sections,
retrieved memories, capability evidence, evaluation confidence, latency,
relationships, goals, intentions, and detected conflicts.

```bash
# Latest interaction
identity debug --id adam

# A specific request, exported as JSON
identity debug --id adam --interaction REQUEST_ID --output debug.json
```

The decision trace is a runtime pipeline trace. It intentionally does not
capture or expose hidden model chain-of-thought. Tool execution is represented
only by actual capability evidence.

Identity Replay combines durable records into a chronological view:

```bash
identity replay --id adam
identity replay --id adam --output replay.json
```

Replay tracks timeline events, beliefs and preferences with evidence,
confidence changes, goals, relationships, identity versions and changelogs,
and ratified constitutional amendments. The JSON `confidence_series` field is
ready for graphing without inventing intermediate state. The web Playground
shows both the latest debugger record and replay timeline in dedicated panels.

