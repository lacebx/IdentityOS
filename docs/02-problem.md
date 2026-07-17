# 02 — Problem Statement

## The Core Problem

AI personalities today are **not portable, not persistent, and not owned by users or developers.**

---

## Three Broken Realities

### 1. Memory is Provider-Locked

When a user chats with ChatGPT over months, memories and preferences accumulate — but they live inside OpenAI's servers. Switch to Claude or Grok and you start from zero. Users are locked in not by the model quality, but by the memory.

### 2. Identity is Shallow

Today's "personality" for an AI agent is just a system prompt. It's a costume, not a soul. Ask most chatbots who they are, and they give you a prompt-level answer. They have no history, no long-term values, no genuine continuity. Override the prompt, and the "personality" disappears.

### 3. Developers Have No Standard

Every developer building an AI agent has to reinvent the wheel:
- How to structure a system prompt for personality
- How to store and retrieve memories
- How to handle identity across multiple sessions
- How to evaluate whether the identity is staying consistent

There is no Docker Compose for "who an agent is." There is no standard identity spec.

---

## The Result

- Users are locked to one provider.
- Developers can't build truly persistent agents.
- AI identities die when you clear your chat history.
- Model upgrades reset everything.
- Nobody owns their AI relationship data.

---

## What's Missing

```
What exists today:
  [User] --> [Model Provider] --> [Response]
                    |
              (memory, identity,
               preferences all locked here)

What needs to exist:
  [User] --> [Identity Runtime] --> [Any Model] --> [Response]
                    |
         (you own memory, identity,
          preferences — portable across models)
```

---

## Why This Is the Right Time to Build It

1. **Model commoditization is happening.** GPT-4 vs Claude 3 vs Gemini Pro are already near-equivalent for most tasks. The model itself is increasingly a commodity. The identity layer is where value accumulates.

2. **AI agent adoption is growing.** More developers are building agents. They all need persistent identity. None of them have a good standard for it.

3. **Users are becoming aware of lock-in.** As AI becomes daily infrastructure, users will want to own their data and relationships, the same way they wanted to own their music library (Spotify vs iTunes) or their contacts (not locked to a phone carrier).

4. **No one has built the standard yet.** This is a foundational infrastructure play, like payment rails before Stripe.
