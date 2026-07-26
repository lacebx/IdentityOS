# Demo 3: Cross-App Continuity

**Goal:** Show an identity remembering facts across different application contexts (ChatGPT → Discord → VS Code → Terminal).

**Approximate time:** 3 minutes

**Emotional arc:** "I told ChatGPT something... Discord remembers it too?" → "The identity owns the memory, not the app."

---

## Prerequisites

- IdentityOS installed
- API key configured
- Runtime server running (`identity playground` or `uvicorn runtime.main:app`)

## Recording Setup

- Terminal 1: Runtime server (background)
- Terminal 2: Client commands (foreground)
- After demonstrating with curl, show the Chrome extension or Discord bot for visual impact

## Step-by-Step

### 1. Start the server

```bash
# Terminal 1
identity playground --port 8765 &
```

### 2. Create an identity

```bash
curl -s -X POST http://localhost:8765/identity \
  -H "Content-Type: application/json" \
  -d '{"identity_id":"lace","name":"Lace","persona":"A helpful assistant"}'
```

Expected output: `{"status":"created","identity_id":"lace"}`

### 3. App A: ChatGPT tells the identity a plan

```bash
curl -s -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "message":"I am moving to Tokyo next month. I need to find an apartment in Shibuya and a Japanese language tutor.",
    "identity_id":"lace",
    "user_id":"chatgpt-web",
    "session_id":"chatgpt-web"
  }'
```

Expected output: The identity acknowledges and stores the Tokyo plan.

### 4. App B: Discord asks without context

Open a **new terminal** (to simulate a different app):

```bash
curl -s -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "message":"What was my moving plan again? I forgot what I told you.",
    "identity_id":"lace",
    "user_id":"discord-bot",
    "session_id":"discord-bot"
  }'
```

**This is the magic moment.** The identity — in a completely different session, pretending to be Discord — remembers the Tokyo plan. The response MUST mention Tokyo, Shibuya, and the language tutor.

### 5. App C: VS Code asks for context

```bash
curl -s -X POST http://localhost:8765/context \
  -H "Content-Type: application/json" \
  -d '{
    "message":"What should I work on today?",
    "identity_id":"lace",
    "user_id":"vscode",
    "session_id":"vscode"
  }'
```

Expected output: Context includes the Tokyo move and any previous facts.

### 6. Show the identity state

```bash
identity inspect --id lace --dashboard
```

Expected output: Dashboard shows the Tokyo-related memories and timeline events.

---

## Visual Alternative (using apps)

If you have the Chrome extension installed, demonstrate the same flow:

1. In ChatGPT tab: "I'm moving to Tokyo next month"
2. In Discord: "What was my moving plan?"
3. Discord response mentions Tokyo

The extension injects identity context into each app's prompt automatically.

---

## Recording Tips

- **Use screen splits** to show both apps communicating with the same identity
- **Label the sessions clearly** — "App A: ChatGPT" and "App B: Discord"
- **Pause after the Discord response** — let the viewer realize the identity remembered across apps
- **Add text overlay** at the key moment: "Same identity. Different app. Full recall."
- **If using curl, add comments** in the terminal to explain each step

---

## Script (if narrating)

> "I told an AI about my Tokyo move in one app. Let me ask a completely different app what my plans are.
> Notice — I never told Discord about Tokyo. The identity remembers because the memory belongs to the identity, not the app.
> This is cross-app continuity. One identity. Any app. Full context."
