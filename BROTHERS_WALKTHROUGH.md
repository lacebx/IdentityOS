# Identity Runtime — Brothers Walkthrough

A complete walkthrough creating 3 brother identities, chatting with each, taking
snapshots, diffing them, and reviewing the ranked experience leaderboard.

---

## 1. Create three brother identities

```bash
# identity-runtime uses --store <dir> for all commands
S="--store test_brothers"

python3 -m cli.main $S create --name "Hector"   --id "hector" --persona "oldest brother, protective leader"
python3 -m cli.main $S create --name "Leonardo" --id "leo"    --persona "middle brother, witty strategist"
python3 -m cli.main $S create --name "Maxwell"   --id "max"    --persona "youngest brother, curious adventurer"
```

**Output:**
```
Identity created.
  id          : hector
  name        : Hector
  persona     : oldest brother, protective leader
  snapshot_id : ac6be73f-5673-46fe-9e36-879085ddf930
  store       : test_brothers

Identity created.
  id          : leo
  name        : Leonardo
  persona     : middle brother, witty strategist
  snapshot_id : ca0c9b2c-154b-45d4-bc4e-16ecb4bbbe5f
  store       : test_brothers

Identity created.
  id          : max
  name        : Maxwell
  persona     : youngest brother, curious adventurer
  snapshot_id : 74a92016-71c5-4863-a37e-63c8b5f1811f
  store       : test_brothers
```

---

## 2. Get all identities (fresh — zero experience)

```bash
python3 -m cli.main $S get
```

**Output:**
```
Rank  ID     Name      Persona                          Exp  Ints  TL  Mem  Rel
---------------------------------------------------------------------------------
1     hector Hector    oldest brother, protective leader  0    0    0    0    0
2     leo    Leonardo  middle brother, witty strategist   0    0    0    0    0
3     max    Maxwell   youngest brother, curious adventurer 0  0    0    0    0

3 identities total.
```

All three identities exist but have no experience yet.

---

## 3. Chat with each brother (via Orchestrator)

A Python script uses `IdentityRuntime` to send 5 messages to each brother so they
learn about each other.

```python
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from core.evaluation import register_default_criteria

store = JSONFileBackend(root_dir="test_brothers")
rt = IdentityRuntime(storage=store)
register_default_criteria(rt.evaluation_engine)
rt.load_persisted()

BROTHERS = {
    "hector": {
        "name": "Hector",
        "messages": [
            "I'm Hector, the oldest of three brothers.",
            "My younger brothers are Leonardo and Max.",
            "I feel responsible for keeping my brothers safe.",
            "Leo is the strategist, always thinking three steps ahead.",
            "Max is fearless, always running off on new adventures.",
        ]
    },
    "leo": {
        "name": "Leonardo",
        "messages": [
            "I'm Leonardo, the middle brother.",
            "My older brother is Hector, my younger is Max.",
            "Hector is strong and protective, I handle the planning.",
            "Max is the youngest and wildest of us three.",
            "Together we make a great team."
        ]
    },
    "max": {
        "name": "Maxwell",
        "messages": [
            "I'm Max, the youngest of three brothers.",
            "Hector is my oldest brother, he looks out for me.",
            "Leo is the middle brother, he's really smart.",
            "I love exploring new places, my brothers always watch my back.",
            "Being the youngest means I get away with more than they did!"
        ]
    }
}

for bid, info in BROTHERS.items():
    sid = rt.start_session(bid)
    for msg in info["messages"]:
        resp = rt.process(InteractionRequest(identity_id=bid, user_input=msg, session_id=sid))
    print(f"  [Session complete: {len(info['messages'])} interactions]")
```

**Output (per session):**
```
--- Session with Hector (hector) ---
  you> I'm Hector, the oldest of three brothers.
  Hector> [No adapter configured. Context prepared for Hector]
  you> My younger brothers are Leonardo and Max.
  Hector> [No adapter configured. Context prepared for Hector]
  you> I feel responsible for keeping my brothers safe.
  Hector> [No adapter configured. Context prepared for Hector]
  you> Leo is the strategist, always thinking three steps ahead.
  Hector> [No adapter configured. Context prepared for Hector]
  you> Max is fearless, always running off on new adventures.
  Hector> [No adapter configured. Context prepared for Hector]
  [Session complete: 5 interactions]

--- Session with Leonardo (leo) ---
  you> I'm Leonardo, the middle brother.
  Leonardo> [No adapter configured. Context prepared for Leonardo]
  you> My older brother is Hector, my younger is Max.
  Leonardo> [No adapter configured. Context prepared for Leonardo]
  you> Hector is strong and protective, I handle the planning.
  Leonardo> [No adapter configured. Context prepared for Leonardo]
  you> Max is the youngest and wildest of us three.
  Leonardo> [No adapter configured. Context prepared for Leonardo]
  you> Together we make a great team.
  Leonardo> [No adapter configured. Context prepared for Leonardo]
  [Session complete: 5 interactions]

--- Session with Maxwell (max) ---
  you> I'm Max, the youngest of three brothers.
  Maxwell> [No adapter configured. Context prepared for Maxwell]
  you> Hector is my oldest brother, he looks out for me.
  Maxwell> [No adapter configured. Context prepared for Maxwell]
  you> Leo is the middle brother, he's really smart.
  Maxwell> [No adapter configured. Context prepared for Maxwell]
  you> I love exploring new places, my brothers always watch my back.
  Maxwell> [No adapter configured. Context prepared for Maxwell]
  you> Being the youngest means I get away with more than they did!
  Maxwell> [No adapter configured. Context prepared for Maxwell]
  [Session complete: 5 interactions]
```

---

## 4. Take snapshots (after chat)

```bash
python3 -m cli.main $S snapshot --id hector --label "after-chat"
python3 -m cli.main $S snapshot --id leo    --label "after-chat"
python3 -m cli.main $S snapshot --id max    --label "after-chat"
```

**Output:**
```
Snapshot captured: 18e7f9fd-6abd-41c6-be7c-48b23bdc3cb0
Snapshot captured: 5de76862-af99-4b02-9c52-09a40eec2e87
Snapshot captured: 3034ca85-9954-497a-884c-c844e988253c
```

Each identity now has 2 snapshots: `initial` and `after-chat`.

---

## 5. Get (ranked) after interactions

```bash
python3 -m cli.main $S get
```

**Output:**
```
Rank  ID     Name      Persona                          Exp  Ints  TL  Mem  Rel
---------------------------------------------------------------------------------
1     max    Maxwell   youngest brother, curious adventurer 17  5    6    6    1
2     hector Hector    oldest brother, protective leader  16  5    6    5    1
3     leo    Leonardo  middle brother, witty strategist   16  5    6    5    1

3 identities total.
```

After chatting, all identities have accumulated experience through interactions,
timeline events, and memories. Max led with 17 total experience.

**Experience breakdown:**
- **Exp** = total experience (interactions + timeline_events + memories)
- **Ints** = interaction count from relationship edges
- **TL** = timeline events
- **Mem** = stored memories
- **Rel** = relationship edges

---

## 6. Snapshot history

```bash
python3 -m cli.main $S history --id hector
python3 -m cli.main $S history --id leo
python3 -m cli.main $S history --id max
```

**Output:**
```
Snapshot history for 'hector' (2 total):
    1. Snapshot ac6be73f [initial] @ 2026-07-20 19:50:47 | modules: experience, identity, knowledge, motivations, relationships, timeline
    2. Snapshot 18e7f9fd [after-chat] @ 2026-07-20 19:50:48 | modules: experience, identity, knowledge, motivations, relationships, timeline

Snapshot history for 'leo' (2 total):
    1. Snapshot ca0c9b2c [initial] @ 2026-07-20 19:50:47 | modules: experience, identity, knowledge, motivations, relationships, timeline
    2. Snapshot 5de76862 [after-chat] @ 2026-07-20 19:50:48 | modules: experience, identity, knowledge, motivations, relationships, timeline

Snapshot history for 'max' (2 total):
    1. Snapshot 74a92016 [initial] @ 2026-07-20 19:50:47 | modules: experience, identity, knowledge, motivations, relationships, timeline
    2. Snapshot 3034ca85 [after-chat] @ 2026-07-20 19:50:48 | modules: experience, identity, knowledge, motivations, relationships, timeline
```

---

## 7. Diff snapshots (initial vs after-chat)

```bash
# Snapshot IDs are taken from history output
python3 -m cli.main $S diff --id hector \
  --from "ac6be73f-5673-46fe-9e36-879085ddf930" \
  --to   "18e7f9fd-6abd-41c6-be7c-48b23bdc3cb0"
```

**Output (all three):**
```
HECTOR diff (initial -> after-chat):
{
  "from_snapshot": "ac6be73f-...",
  "to_snapshot":   "18e7f9fd-...",
  "identity_id":   "hector",
  "elapsed_seconds": 0.66,
  "change_count": 0,
  "changes": []
}

LEO diff (initial -> after-chat):
{
  "from_snapshot": "ca0c9b2c-...",
  "to_snapshot":   "5de76862-...",
  "identity_id":   "leo",
  "elapsed_seconds": 0.68,
  "change_count": 0,
  "changes": []
}

MAX diff (initial -> after-chat):
{
  "from_snapshot": "74a92016-...",
  "to_snapshot":   "3034ca85-...",
  "identity_id":   "max",
  "elapsed_seconds": 0.65,
  "change_count": 0,
  "changes": []
}
```

> **Note:** `change_count: 0` because snapshots capture the static identity
> specification (modules config), not the evolving runtime data (timeline events,
> memories, relationships). The runtime data is persisted separately and is
> visible via `inspect` and `rank`.

---

## 8. Inspect final state

```bash
python3 -m cli.main $S inspect --id hector
```

**Output (Hector shown, others similar):**
```
{
  "identity": {
    "id": "hector",
    "name": "Hector",
    "persona": "oldest brother, protective leader",
    "created_at": 1784577047.5194337,
    "version": "0.1.0"
  },
  "timeline": {
    "event_count": 6,
    "events": [
      {"title": "Identity Created", "event_type": "creation", ...},
      {"title": "Interaction", "event_type": "milestone", ...},
      ...
    ]
  },
  "relationships": {
    "edge_count": 1,
    "edges": [
      {"source": "hector", "target": "98467aba-...", "type": "peer", "strength": 1.0}
    ]
  },
  "goals": {
    "goal_count": 0,
    "goals": []
  },
  "memories": {
    "total": 5,
    "recent": [
      {"content": "User: I'm Hector, the oldest of three brothers...", "type": "episodic", ...},
      ...
    ]
  }
}
```

---

## Runtime state summary

| Identity | Interactions | Timeline | Memories | Relationships | **Experience** |
|----------|:-----------:|:--------:|:--------:|:------------:|:--------------:|
| Hector   | 5           | 6        | 5        | 1            | **16**         |
| Leonardo | 5           | 6        | 5        | 1            | **16**         |
| Maxwell  | 5           | 6        | 6        | 1            | **17**         |

All 3 identities now have persistent timelines, episodic memories, relationship
edges, and ranked experience — demonstrating the core identity lifecycle.

---

## 9. API verification — all identities visible

```bash
# Start the API server and list identities
python3 -m runtime.main &
curl -s http://127.0.0.1:8765/identity
```

**Response:**
```json
{
    "identities": [
        "hector",
        "leo",
        "max",
        "mentor-mrs3q8op"
    ]
}
```

The `/identity` endpoint now merges identities from both runtime memory and
persistent storage, so CLI-created identities appear even before they are loaded.  
Individual identity details are available at `/identity/{id}`:

```bash
curl -s http://127.0.0.1:8765/identity/hector | python3 -m json.tool
```
