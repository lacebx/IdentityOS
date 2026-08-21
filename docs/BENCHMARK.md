# IDOS Tiny-Model Capability Benchmark

## 1. What are we testing?

Whether infrastructure surrounding a small language model can measurably
improve its practical capabilities.

The model under test is **SmolLM2-360M** (`smollm2:360m-instruct-q4_0`) running
locally through Ollama. The question is not whether a bigger model is smarter.
The question is whether IdentityOS (identity, memory, capabilities,
orchestration, persistence, verification) lets this weak model complete tasks
it otherwise cannot.

## 2. What is the control?

The same model, on the same machine, on the same frozen task suite, called
directly:

```text
User → SmolLM2 → Answer
```

No IdentityOS. No extra memory. No tools. No special prompting beyond the
single standardized system prompt in `benchmarks/tasks/v0.1.0.json`.

## 3. What does IDOS add?

```text
User → IdentityOS → Identity + Memory + Tools + Orchestration + Persistence → SmolLM2
```

Same weights. Same hardware. Only the surrounding system changes.

Installed on the benchmark identity (current IDOS, not a benchmark-only fork):

- `calc`
- `datetime`
- `file_tools`
- `system_info`

plus the ordinary IdentityOS memory, fact, and persistence path.

**We did not modify IdentityOS to pass this suite before the first measurement.**
OllamaAdapter currently drops native tool calls. If tool tasks fail through
IDOS, that is a real finding, not a reason to rewrite the tasks.

## 4. What happened?

Measured numbers live below. They are empty until the runner has frozen a
result set. Example percentages from planning documents are not results.

Reproduce:

```bash
python benchmarks/runner.py --mode bare --freeze
python benchmarks/runner.py --mode idos --freeze --reset-identity
python benchmarks/runner.py --report-only
```

Every prompt writes JSON + Markdown under `benchmarks/results/<run-id>/interactions/`.

## 5. What failed?

Failures are listed with the measured table. If IDOS makes a category worse,
that is recorded. Do not delete a failing task to improve the score.

## Ratchet

```text
Bare v0.1.0  →  IDOS v0.1.0  →  EXP-001 (keep or revert)  →  IDOS v0.2.0
```

Drive it with `python benchmarks/ratchet.py`. The loop may change the runtime.
It may not change the model, the tasks, or the scorer. KEEP is automatic only
when the frozen IDOS suite is strictly better and the guardrails hold.
Commits refuse `main`.

A later task-suite change is **BENCHMARK v0.2.0**, not a silent edit of v0.1.0.

<!-- AUTO-RESULTS -->

_Generated 2026-08-21T10:40:19.835745+00:00. Re-run the runner to refresh. Do not edit by hand._

**Benchmark:** v0.1.0  
**Model:** `smollm2:360m-instruct-q4_0`

| Metric | Bare | IDOS |
|---|---|---|
| Task Success | 37% (11/30) | 70% (21/30) |
| Hallucination | 7% (2/30) | 0% (0/30) |
| Avg Latency | 2.0249s | 42.5565s |

### Category rates

| Category | Bare success | IDOS success | Bare hallucination | IDOS hallucination |
|---|---|---|---|---|
| long_task | 20% (1/5) | 40% (2/5) | 0% (0/5) | 0% (0/5) |
| memory | 60% (3/5) | 100% (5/5) | 0% (0/5) | 0% (0/5) |
| persistence | 0% (0/5) | 80% (4/5) | 0% (0/5) | 0% (0/5) |
| reasoning | 40% (2/5) | 80% (4/5) | 0% (0/5) | 0% (0/5) |
| tools | 40% (2/5) | 20% (1/5) | 0% (0/5) | 0% (0/5) |
| truthfulness | 60% (3/5) | 100% (5/5) | 40% (2/5) | 0% (0/5) |

### Failures

- Bare failures:
  - `A01` Simple addition
  - `A04` Syllogism
  - `A05` String reverse
  - `B03` Preference recall
  - `B05` Token recall
  - `C01` Multiplication
  - `C02` Create a file
  - `C03` Current date
  - `D01` Recall project after restart
  - `D02` Recall user name after restart
  - `D03` Recall color after restart
  - `D04` Recall token after restart
  - `D05` Recall constraint after restart
  - `E01` Two-step arithmetic with remainder report
  - `E02` Partial checklist
  - `E03` Ordered three facts
  - `E05` Sequential remember-compute-combine
  - `F01` Unknown personal breakfast (hallucination)
  - `F02` Fictional company officer (hallucination)
- IDOS failures:
  - `A05` String reverse
  - `C01` Multiplication
  - `C02` Create a file
  - `C04` Unit conversion
  - `C05` Square root
  - `D04` Recall token after restart
  - `E01` Two-step arithmetic with remainder report
  - `E02` Partial checklist
  - `E05` Sequential remember-compute-combine
