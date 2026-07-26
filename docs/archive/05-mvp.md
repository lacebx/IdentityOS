# 05 — MVP

## MVP Goal

> **Prove the thesis: one identity, running across two different LLMs, maintaining continuity.**

The MVP is not the marketplace. Not the SDK. Not the registry. Those come later.

The MVP is a single working demo that shows: *the same AI identity, starting a conversation on ChatGPT, continuing on Grok, and feeling like the same continuous mind.*

---

## MVP Scope

### What's In

1. **Identity Runtime Service** (simple Node.js/Python backend)
   - Load an identity spec from a local JSON file
   - Store memories in a simple vector store (pgvector or local FAISS)
   - API endpoints: `POST /context`, `POST /evaluate`

2. **Chrome Extension (Bridge)**
   - Content script on chatgpt.com and grok.com
   - Intercepts outgoing messages
   - Calls Runtime to get context
   - Prepends context to message
   - Intercepts responses
   - Calls Runtime to evaluate and store memories

3. **One Identity**
   - A single demo identity (e.g., "Startup Mentor")
   - Defined as a JSON spec file
   - Has personality, values, and starting knowledge

4. **Demo Script**
   - Start a chat on ChatGPT with the identity active
   - Make several exchanges (establish some preferences/history)
   - Switch to Grok
   - Show the identity remembers the context from ChatGPT

### What's NOT In MVP

- No user accounts or auth
- No marketplace or registry
- No SDK
- No mobile app
- No monetization
- No OpenAI API key required (extension works with chat UI, not API)

---

## Technical Stack (MVP)

| Layer | Technology |
|---|---|
| Runtime API | Node.js (Express) or Python (FastAPI) |
| Memory Store | SQLite + local embeddings (no external DB needed) |
| Embeddings | `nomic-embed-text` via Ollama (free, local) |
| Extension | Vanilla JS (Manifest V3 Chrome Extension) |
| Identity Spec | JSON file |
| Deployment | Local (localhost runtime + extension loaded from disk) |

No API keys needed for MVP. No external services. Everything runs locally.

---

## MVP API Endpoints

```
POST /context
  Body: { message: string, identity_id: string, user_id: string }
  Returns: { augmented_context: string }

POST /evaluate
  Body: { message: string, response: string, identity_id: string, user_id: string }
  Returns: { memories_stored: number, summary: string }

GET /identity/:id
  Returns: { identity spec }

GET /memories/:user_id/:identity_id
  Returns: { memories: Memory[] }
```

---

## Success Criteria for MVP

- [ ] Extension installs cleanly in Chrome
- [ ] Extension intercepts ChatGPT messages without breaking the UI
- [ ] Identity context is prepended to messages (verifiable in Network tab)
- [ ] Memories are stored after conversations
- [ ] Switching to Grok: same identity context is used
- [ ] Demo: "Remember when I told you I prefer TypeScript?" — identity confirms it does

---

## What the Demo Should Show

```
[ChatGPT - Day 1]
User: "Help me decide between TypeScript and Python for my new project."
[Identity context prepended, Startup Mentor identity active]
Startup Mentor: "For a new project in 2026, I'd lean TypeScript unless..."
User: "Yeah I agree, let's go TypeScript."
[Memory stored: user prefers TypeScript for new projects]

[Grok - Day 2 or same session]
User: "What stack should I use for the backend?"
[Memory retrieved: user prefers TypeScript]
Startup Mentor: "Given your preference for TypeScript, I'd suggest..."
```

The magic: the user never set up any preferences manually. The identity *learned* it through conversation. And it followed them across models.
