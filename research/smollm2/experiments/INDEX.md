# Experiment Index — SmolLM2 × IdentityOS Ratchet

All experiments run on `smollm2:360m-instruct-q4_0` via Ollama, frozen 30-task suite v0.1.0.
"Before" and "After" refer to overall task success rate. Δ is change in successful tasks.

---

## Score progression

```
Bare SmolLM2-360M baseline: 37% (11/30) ← frozen comparator (NOT a ratchet step)

IDOS ratchet (each step measured against prior IDOS state):

  EXP-001  bootstrap   —→ 17%   first IDOS measurement (below bare; no runtime tuning)
      ↓
  EXP-002  KEEP    17%→ 30%   +4 tasks
      ↓
  EXP-003  KEEP    30%→ 50%   +6 tasks   ← IDOS first approaches bare baseline region
      ↓
  [EXP-004–008 reverted / not in KEEP chain]
      ↓
  EXP-009  KEEP    50%→ 67%   +5 tasks   ← IDOS clearly exceeds bare (67% vs 37%)
      ↓
  [EXP-010–018 reverted]
      ↓
  EXP-019  KEEP    67%→ 70%   +1 task
      ↓
  EXP-020  KEEP    70%→ 73%   +1 task
      ↓
  [EXP-021–025 reverted]
      ↓
  EXP-026  KEEP    73%→ 77%   +1 task    ← current proven tip (23/30)
      ↓
  [EXP-027–031 in progress / reverted]
```

---

## Full index table

| Exp | Verdict | Before | After | Δ tasks | Halluc | Latency | Key change |
|-----|---------|--------|-------|---------|--------|---------|------------|
| EXP-001 | BOOTSTRAP | — | 17% (5/30) | +5 | 0 | 91.5 s | First IDOS measurement |
| EXP-002 | **KEEP** | 17% | 30% (9/30) | +4 | 0 | 63.1 s | OllamaAdapter inherits OpenAI tool-call loop |
| EXP-003 | **KEEP** | 30% | 50% (15/30) | +6 | 0 | 57.4 s | Tool-intent gating (only gate tool loop when needed) |
| EXP-004 | REVERT | 50% | — | — | — | — | Persistence attempt; harness abort |
| EXP-005 | REVERT | 50% | 73% | — | FAIL | — | Remember directives + profile recall; hallucination gate fail |
| EXP-006 | REVERT | 50% | — | — | — | — | Variant of EXP-005 with topic whitelist |
| EXP-007 | REVERT | 50% | — | — | — | — | Variant of EXP-005 with SSN abstain |
| EXP-008 | REVERT | 50% | 67% | +5 | 0 | 55.1 s | Recall stack (reverted: not clean from HEAD) |
| EXP-009 | **KEEP** | 50% | 67% (20/30) | +5 | 0 | 37.7 s | Profile recall + generic explicit-abstain |
| EXP-010 | REVERT | 67% | 63% | −2 | 0 | 38.5 s | Strip SmolLM prompt echoes — hurt more than helped |
| EXP-011 | REVERT | 67% | 77% | +3 | 0 | 47.9 s | Temperature 0.7→0.0 — latency gate fail (47.9 > 47.1) |
| EXP-012–017 | REVERT | 67–73% | various | — | — | — | Tool-call parsing variants; none cleared all gates |
| EXP-018 | REVERT | 67% | 63% | −2 | 0 | 38.5 s | Tool retry/re-prompt variant |
| EXP-019 | **KEEP** | 67% | 70% (21/30) | +1 | 0 | 42.6 s | Tool-call retry when no call emitted |
| EXP-020 | **KEEP** | 70% | 73% (22/30) | +1 | 0 | 41.1 s | Improved tool-call extraction + re-prompt loop |
| EXP-021–024 | REVERT | 73% | various | — | — | — | Tool variant experiments |
| EXP-025 | REVERT | 73% | 63% | −4 | 0 | 43.8 s | Broke tool category |
| EXP-026 | **KEEP** | 73% | **77% (23/30)** | +1 | 0 | 38.0 s | Tool-use reminder in system prompt when tool available |
| EXP-027 | REVERT | 77% | — | — | — | — | Orchestrator edit (bad search string) |
| EXP-028 | REVERT | 77% | — | — | — | — | Variant; apply fail |
| EXP-029 | REVERT | 77% | 70% | −2 | 0 | — | System prompt addition dropped tools 3→1 |
| EXP-030 | REVERT | 77% | 63% | −4 | 0 | 40.5 s | Verify directive — tools collapsed 3→1 |
| EXP-031 | **REVERT** | 77% | 67% (20/30) | −3 | 0 | 42.1 s | Verify directive variant — long_task 2/5→0/5; A03 regression |

---

## Notes on gaps

- EXP-004–008 are partially documented; some were abandoned due to harness dirty-tree aborts
  before producing clean ratchet artifacts.
- EXP-011 achieved 77% success but was REVERTed due to latency gate (47.9 s > 1.25× 37.7 s).
  The same 77% was later reached cleanly in EXP-026.
- The autopilot system introduced from EXP-012 onward generates many apply-failures
  (DeepSeek proposing nonexistent symbols). These are loop iterations, not full ratchet runs.
