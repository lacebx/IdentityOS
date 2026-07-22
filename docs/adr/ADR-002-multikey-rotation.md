# ADR-002: Multi-Key LLM Provider Rotation

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** N/A (Infrastructure)

---

## Context

The system depends on an LLM provider (Groq) for identity mutation decisions, response generation, and behavior enforcement. A single API key presents a single point of failure.

## Decision

Implement multi-key rotation with cooldown. The adapter maintains a pool of API keys. On request, it uses the first non-cooldown key. On rate limit, it marks the key with a cooldown duration and rotates to the next key.

## Rationale

1. **Resilience** — Rate limits on one key do not block the system.
2. **Self-healing** — Cooldown durations are extracted from response headers.
3. **Simplicity** — Round-robin with cooldown is easy to reason about and debug.
4. **Visibility** — Cooldown state is inspectable via the status endpoint.

## Consequences

- Positive: Near-zero downtime from rate limits under normal conditions
- Positive: Six keys provide substantial headroom
- Negative: Token usage statistics must be aggregated across keys
- Negative: If all keys are simultaneously on cooldown, the system must wait

## Compliance

- `adapters/groq_adapter.py` — `_get_available_key()`, `_apply_cooldown()`, `GROQ_API_KEY_1`–`GROQ_API_KEY_6`
