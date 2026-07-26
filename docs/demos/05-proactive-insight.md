# Demo 5: Proactive Insight (Hero Demo)

**Goal:** Show the identity noticing something the user missed — connecting two facts from different contexts and proactively flagging a broken plan.

**Approximate time:** 3 minutes

**Emotional arc:** Innocuous facts → "Wait, that doesn't add up" → "It caught what I missed" → **holy shit moment**

---

## Prerequisites

- IdentityOS installed
- API key configured
- Runtime server running on localhost:8765

## Recording Setup

- Terminal 1: Runtime server logs (background)
- Terminal 2: curl commands (foreground)
- Terminal 3: Dashboard inspect (foreground, for the reveal)

---

## Step-by-Step

### 1. Start the server

```bash
# Terminal 1
identity playground --port 8765 &
```

### 2. Clean state + create identity

```bash
rm -rf .identity_store

curl -s -X POST http://localhost:8765/identity \
  -H "Content-Type: application/json" \
  -d '{
    "identity_id":"oracle",
    "name":"Oracle",
    "persona":"A proactive analyst who connects facts across conversations"
  }'
```

### 3. Session A: User shares promotion plan

```bash
curl -s -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "message":"I am up for promotion at work. My promotion depends on shipping Project A by end of quarter. I have been working on it for months.",
    "identity_id":"oracle",
    "user_id":"planning-session",
    "session_id":"planning-session"
  }'
```

Expected: Oracle acknowledges the promotion plan and its dependency on Project A.

### 4. Simulate time passing

```bash
# Store a memory that the user "said this a while ago"
curl -s -X POST http://localhost:8765/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "message":"My promotion depends on shipping Project A",
    "response":"I will help you track Project A progress.",
    "identity_id":"oracle",
    "user_id":"planning-session",
    "session_id":"planning-session"
  }'
```

### 5. Session B: Different day, different app — user mentions cancellation

```bash
curl -s -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Project A got cancelled yesterday. The whole team is being reassigned to Project B starting next week.",
    "identity_id":"oracle",
    "user_id":"discord-chat",
    "session_id":"discord-chat"
  }"
```

Expected: Oracle stores this fact.

### 6. Session C: User asks an innocent question

```bash
curl -s -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "message":"What should I focus on this week?",
    "identity_id":"oracle",
    "user_id":"vscode",
    "session_id":"vscode"
  }"
```

**This is the climax.** Oracle should:
1. Recall Project A = promotion dependency (from Session A)
2. Recall Project A was cancelled (from Session B)
3. Connect these facts
4. **Proactively warn the user** that their promotion plan needs attention

Expected response (paraphrased):
> "Your promotion depends on Project A, but Project A was cancelled. You may want to discuss an alternative promotion path with your manager, or propose Project B as your new flagship deliverable."

### 7. Show the insight in the dashboard

```bash
identity inspect --id oracle --dashboard
```

Expected dashboard shows:
- Goal: "Ship Project A for promotion"
- Fact: Project A was cancelled
- Timeline events connecting both conversations
- The contradiction is visible

---

## The Emotional Punch

This is the demo people will remember. The user:
- Never asked Oracle to connect the dots
- Never said "check if my plan still works"
- Just asked "what should I focus on?"

Oracle independently:
1. Remembered the promotion dependency
2. Remembered the cancellation
3. Realized the plan is broken
4. Warned the user

**This is what no isolated AI can do.** ChatGPT only knows the promotion plan. Discord only knows the cancellation. Oracle — the persistent identity — knows both and connects them.

---

## Recording Tips

- **This is the hero demo.** Spend time on it.
- **Use music.** Start neutral, build tension at Step 5, climax at Step 6.
- **Use screen annotations.** Highlight key phrases in the response:
  - "Project A" (from memory)
  - "cancelled" (from later memory)
  - "promotion depends on it" (the connection)
- **Pause for 3 seconds** after the response appears — let it sink in.
- **Record the dashboard** at the end to show the evidence physically stored.
- **If possible, show three app windows** (ChatGPT, Discord, VS Code) with the Chrome extension injecting context — the visual of three apps sharing one identity is powerful.

---

## Script (if narrating)

> "I told Oracle about my promotion. It depends on Project A. Months of work.
> Later, in a completely different conversation, I mentioned Project A was cancelled.
> Now I ask a simple question: 'What should I focus on?'
> Oracle pauses... and says something no single AI could know.
> 'Your promotion depends on Project A. Project A was cancelled. Your plan is broken.'
> Oracle connected two facts across two conversations. It noticed what I missed. It changed what I do next.
> That's the power of a persistent identity."
