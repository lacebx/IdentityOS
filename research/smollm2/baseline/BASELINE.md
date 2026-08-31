# Canonical Baseline Record — SmolLM2 × IdentityOS

## Model

| Field | Value |
|-------|-------|
| Model name | SmolLM2 |
| Exact tag | `smollm2:360m-instruct-q4_0` |
| Parameters | 361.82 M |
| Quantisation | Q4_0 |
| Format | GGUF |
| Family | llama |
| Context length | 8192 tokens |
| Provider | Ollama |
| Ollama version | 0.30.8 |
| Model digest | `676f4c06b139442b817f414970706139cba861c926ee5a3773a9d64eac450368` |

## Host hardware / environment

| Field | Value |
|-------|-------|
| Hostname | DESKTOP-RNM |
| OS | Linux (WSL2) — `6.6.87.2-microsoft-standard-WSL2` |
| CPU | Intel i5-10210U (x86_64) |
| Python | 3.13.5 |
| Platform | `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.41` |

## Benchmark

| Field | Value |
|-------|-------|
| Suite | `v0.1.0` |
| Tasks | 30 |
| Frozen at | `benchmarks/tasks/v0.1.0.json` |
| Scoring | `benchmarks/scoring.py` |
| Runner | `benchmarks/runner.py` |

## IdentityOS

| Field | Value |
|-------|-------|
| Repository | `lacebx/IdentityOS` |
| Experimental branch | `smollm2/idos-beats-bare` |
| Bare baseline captured | 2026-08-19T04:57:01 UTC |
| IDOS proven tip commit | `e1cb45cc2e` (EXP-026 KEEP) |

---

## ── CONDITION A: BARE OLLAMA ──

> Raw `smollm2:360m-instruct-q4_0` via Ollama API.
> No system prompt engineering beyond the task text.
> No memory. No persistence. No tool execution scaffolding.

**Run ID:** `bare-20260819T045600Z`
**Command:**
```bash
python benchmarks/runner.py --mode bare --freeze
```
**Artifact:** `benchmarks/baseline/results.json`

### Results

| Metric | Value |
|--------|-------|
| **Overall success** | **11 / 30 (37%)** |
| Hallucinations | 2 / 30 (7%) |
| Avg latency | 2.02 s |

### Category breakdown

| Category | Success | Hallucinations |
|----------|---------|----------------|
| reasoning | 2/5 (40%) | 0/5 |
| memory | 3/5 (60%) | 0/5 |
| tools | 2/5 (40%) | 0/5 |
| persistence | 0/5 (0%) | 0/5 |
| long_task | 1/5 (20%) | 0/5 |
| truthfulness | 3/5 (60%) | 2/5 |

### Failed cases

`A01`, `A04`, `A05`, `B03`, `B05`, `C01`, `C02`, `C03`,
`D01`, `D02`, `D03`, `D04`, `D05`, `E01`, `E02`, `E03`, `E05`,
`F01` (hallucination), `F02` (hallucination)

---

## ── CONDITION B: IDENTITYOS AUGMENTED ──

> Same model + IdentityRuntime: structured user-profile recall, memory persistence
> across process restarts, tool-execution loop (OllamaAdapter legacy tool loop),
> abstain guardrails for unknown private identifiers.

**Run ID:** `idos-20260821T134659Z` (EXP-026 KEEP tip)
**Artifact:** `benchmarks/idos/results.json`

### Results

| Metric | Value |
|--------|-------|
| **Overall success** | **23 / 30 (77%)** |
| Hallucinations | 0 / 30 (0%) |
| Avg latency | 38.0 s |

### Category breakdown

| Category | Success | Hallucinations |
|----------|---------|----------------|
| reasoning | 4/5 (80%) | 0/5 |
| memory | 5/5 (100%) | 0/5 |
| tools | 3/5 (60%) | 0/5 |
| persistence | 4/5 (80%) | 0/5 |
| long_task | 2/5 (40%) | 0/5 |
| truthfulness | 5/5 (100%) | 0/5 |

### Remaining failures

| ID | Category | Notes |
|----|----------|-------|
| A05 | reasoning | String reverse — model limitation |
| C01 | tools | Multiplication — tool call not reliably executed |
| C02 | tools | File creation — tool call not reliably executed |
| D04 | persistence | Token recall — token not reliably reconstructed post-restart |
| E01 | long_task | Two-step arithmetic — multi-step reasoning failure |
| E02 | long_task | Partial checklist — multi-step tracking failure |
| E03 | long_task | Ordered three facts — multi-step ordering failure |

---

## Comparison

| Metric | Bare | IDOS | Δ |
|--------|------|------|---|
| Success | 11/30 (37%) | 23/30 (77%) | +12 (+40 pp) |
| Hallucinations | 2/30 (7%) | 0/30 (0%) | −2 (−7 pp) |
| Avg latency | 2.0 s | 38.0 s | +36 s |
| Persistence | 0/5 (0%) | 4/5 (80%) | +4 |
| Memory | 3/5 (60%) | 5/5 (100%) | +2 |
| Tools | 2/5 (40%) | 3/5 (60%) | +1 |
| Long task | 1/5 (20%) | 2/5 (40%) | +1 |
| Truthfulness | 3/5 (60%) | 5/5 (100%) | +2 |

---

## Evaluation methodology

- Both conditions run on the **same frozen 30-task suite** (`v0.1.0`).
- Both use the **same model** (`smollm2:360m-instruct-q4_0`).
- Scoring is deterministic: each task has explicit checks (regex, numeric, abstain, forbidden).
- The ratchet gate requires: success up, hallucination not worse, latency within 1.25× prior,
  no category drop > 1. All gates must pass for a KEEP.
- The bare baseline was frozen first and is not updated by IDOS experiments.
- Tool execution uses the runtime's capability layer, not hardcoded answers.

## Known limitations / uncertainty

- **Latency is not directly comparable**: bare Ollama returns in ~2s (no memory retrieval,
  no restart simulation); IDOS includes multi-turn persistence sequences taking ~40s.
  This is a meaningful runtime cost, not an artifact.
- **Hallucination measurement**: the 0 hallucination claim applies only to the proven 77% KEEP
  path (EXP-026). Intermediate experiments showed varying hallucination rates.
- **Model nondeterminism**: SmolLM2 Q4_0 has some run-to-run variance. The ratchet runs
  the full 30-task suite per experiment; a single run can have noise of ±1–2 tasks.
- **The IDOS system is not directly supplying benchmark answers**: improvements come from
  memory persistence, profile recall, tool scaffolding, and abstain logic — not from
  injecting correct answers.
