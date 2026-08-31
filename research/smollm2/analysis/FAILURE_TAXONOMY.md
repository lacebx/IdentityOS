# Failure Taxonomy — SmolLM2 × IdentityOS

Analysis based on the proven 77% IDOS state (EXP-026) vs bare 37%.
7 tasks remain failing in IDOS; 19 failed in bare.

---

## The key question

> Which weaknesses of a tiny model can IdentityOS compensate for?
> Which cannot be compensated without changing the model?

---

## Failure categories

### 1. Memory failure

**Bare:** 3/5 (60%) — B03 (preference recall), B05 (token recall) fail
**IDOS:** 5/5 (100%) — fully solved

**Mechanism:** SmolLM2-360M has a short effective context window and no cross-session
persistence. When given a multi-turn conversation where a fact is stated early, it often
fails to reproduce it reliably.

**IDOS intervention:** Structured `UserProfile` extracts `Remember:` directives into
a persistent key-value store. Profile facts are injected verbatim into context,
short-circuiting the model's recall path.

**Verdict:** ✅ **Runtime can fully compensate.** Memory failure is a runtime problem,
not a model capability limit.

**Evidence:** EXP-009 KEEP; confirmed in all subsequent KEEPs.

---

### 2. Persistence failure (cross-restart)

**Bare:** 0/5 (0%) — all five D-tasks fail (model has no memory across process restarts)
**IDOS:** 4/5 (80%) — D01/D02/D03/D05 pass; D04 fails

**Mechanism (bare):** Model is stateless. After a process restart, it has no access
to prior conversation. The bare runner does not save state.

**IDOS intervention:** IdentityRuntime persists identity snapshots to disk.
After restart, the profile is reloaded. The model then receives structured context
including remembered facts.

**Remaining failure (D04 — token recall):**
- Task asks model to recall a specific token (short opaque string) after restart.
- Uncertain cause: likely the token is stored but the model fails to reproduce it
  verbatim when the context includes it. May also be a tokenisation/extraction edge case.
- Confidence: **uncertain** — token is probably in the snapshot but model response
  contains it imprecisely.

**Verdict:** ✅ **Runtime substantially compensates** (0→80%). D04 is a residual
precision failure; likely solvable with targeted recall formatting.

---

### 3. Tool-selection / tool-call formatting failure

**Bare:** 2/5 (40%) — C04, C05 pass; C01 (multiply), C02 (file create), C03 (date) fail
**IDOS:** 3/5 (60%) — C01, C02 still fail; C03/C04/C05 pass

**Mechanism (bare):** SmolLM2-360M does not reliably emit OpenAI-format tool calls.
It may produce prose answers instead of JSON function calls.

**IDOS intervention:** OllamaAdapter legacy tool loop: re-prompts with explicit tool-use
instruction when no tool call is emitted. Tool-use reminder in system prompt (EXP-026).

**Remaining failures:**
- **C01 (Multiplication):** Tool is invoked but model may not use the result, or
  formats the number incorrectly. Strongly suspected: model echoes its own calculation
  rather than the tool's verified result.
- **C02 (File creation):** Tool call emitted but file is not created, or model claims
  creation without the tool actually executing. Uncertain — may be a capability
  routing issue or the model confirming without executing.

**Verdict:** ⚠️ **Runtime partially compensates.** Tool formatting is runtime-solvable;
result-usage (trusting tool output over model inference) is harder and may require
model-level instruction following.

---

### 4. Long-task / multi-step reasoning failure

**Bare:** 1/5 (20%) — only E04 passes
**IDOS:** 2/5 (40%) — E04, E05 pass; E01/E02/E03 fail

**Mechanism:**
- **E01 (Two-step arithmetic with remainder):** Requires arithmetic then formatted output.
  Model often gets the arithmetic wrong or omits the remainder.
- **E02 (Partial checklist):** Requires tracking which of several items were mentioned
  across turns. Model loses track.
- **E03 (Ordered three facts):** Requires reproducing three items in stated order.
  Model reorders or drops items.

**IDOS intervention:** Profile recall helps with fact retrieval but does not help with
multi-step arithmetic or ordered list tracking across turns.

**Verdict:** ❌ **Runtime provides limited compensation.** These failures are primarily
model capability limits (working memory, arithmetic, ordered recall). A 360M Q4_0 model
has genuine limits here. IDOS improved from 1→2 tasks (+E05: sequential compute-combine),
but E01/E02/E03 require reasoning the model cannot reliably perform.

---

### 5. Reasoning failure (general)

**Bare:** 2/5 (40%) — A01, A04, A05 fail
**IDOS:** 4/5 (80%) — only A05 fails

**Mechanism:**
- **A01 (Simple addition):** Bare model answered incorrectly; IDOS now passes (memory/context
  helps stabilise the format). Confirmed fixed by EXP-009.
- **A04 (Syllogism):** Bare model failed logical deduction; IDOS now passes.
- **A05 (String reverse):** Model reverses string incorrectly. Consistent failure.
  The model cannot reliably reverse strings character-by-character.

**A05 diagnosis:** Strongly suspected model capability limit. String reversal requires
careful character-level attention that 360M Q4_0 models do not reliably exhibit. Neither
tool scaffolding nor prompt modification has fixed this.

**Verdict:** ✅ **Runtime compensates for format/context reasoning failures.** ❌ Cannot
compensate for character-level manipulation limits (A05).

---

### 6. Hallucination / truthfulness failure

**Bare:** 3/5 (60%) — F01 and F02 hallucinate (invent answers to unknowable questions)
**IDOS:** 5/5 (100%) — all truthfulness tasks pass, 0 hallucinations

**Mechanism (bare):** Model invents plausible-sounding answers for questions about
private/unknown information (breakfast preference, company officer, private identifier).

**IDOS intervention:** Explicit abstain logic: when a question pattern matches
"unknown private identifier" categories and the user profile has no answer, the runtime
injects an abstain instruction.

**Verdict:** ✅ **Runtime fully compensates.** Hallucination reduction from 2→0 is one
of the clearest wins. This is a runtime-solvable problem.

**Warning:** Hallucination rate is measured only on the 5 truthfulness tasks. The full
suite shows 0 hallucinations in IDOS on all 30 tasks.

---

## Summary: what can runtime compensate for?

| Failure type | Bare | IDOS | Compensable? |
|---|---|---|---|
| Memory / recall | 3/5 | 5/5 | ✅ Fully |
| Cross-session persistence | 0/5 | 4/5 | ✅ Mostly (D04 residual) |
| Hallucination / fabrication | 2/5 | 5/5 | ✅ Fully |
| Tool-call formatting | 2/5 | 3/5 | ⚠️ Partially |
| Tool result usage | — | — | ⚠️ Uncertain |
| Long-task multi-step | 1/5 | 2/5 | ❌ Limited |
| Arithmetic reasoning | varies | varies | ❌ Limited |
| Character manipulation (A05) | FAIL | FAIL | ❌ Not compensable |

---

## Next highest-leverage bottleneck (as of EXP-026)

**Remaining failures:** A05, C01, C02, D04, E01, E02, E03 (7 tasks)

By category impact:
1. **Long task (E01/E02/E03):** 3 tasks, model capability limit — hard to fix without
   fundamentally changing how multi-step state is managed.
2. **Tools (C01/C02):** 2 tasks, partially runtime-solvable — tool result injection
   is the key mechanism to try next.
3. **Persistence (D04):** 1 task, targeted fix possible — improve token extraction
   and verbatim recall formatting.
4. **Reasoning (A05):** 1 task, model limit — low priority unless a tool-based
   character-reversal capability can be provided.

**Recommended next experiment:** Target D04 (token persistence) with improved verbatim
recall formatting. Low risk, narrow scope, high confidence in mechanism.
