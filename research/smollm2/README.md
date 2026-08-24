# SmolLM2 × IdentityOS — Research Line

**Research question:** Can an identity/runtime layer materially improve the reliability and
usefulness of a very small local language model, without changing the model itself?

**Model under test:** `smollm2:360m-instruct-q4_0` via Ollama (361 M parameters, Q4_0 quantisation)

**Experimental branch:** `smollm2/idos-beats-bare`

---

## Core claim (as of 2026-08-21, EXP-026 KEEP)

| Condition | Success | Hallucinations | Avg latency |
|-----------|---------|----------------|-------------|
| **Bare Ollama** | 11/30 (37%) | 2/30 (7%) | 2.0 s |
| **IdentityOS augmented** | 23/30 (77%) | 0/30 (0%) | 38.0 s |
| **Δ** | **+12 tasks (+40 pp)** | **−2 (−7 pp)** | +36 s |

Claim: *IdentityOS + SmolLM2-360M substantially outperforms bare SmolLM2-360M on
a frozen 30-case benchmark, with no hallucinations on the proven KEEP path.*

---

## Important distinctions

- **Bare model** = raw Ollama API, no system prompt engineering beyond task text, no
  memory, no persistence, no tool execution scaffolding.
- **IDOS augmented** = same model + IdentityRuntime: structured memory/profile recall,
  persistence across restarts, tool-execution loop, abstain guardrails.
- The latency increase is expected and acceptable: the runtime adds multi-turn
  restart/recall sequences. The bare model returns immediately but without persistence.
- The benchmark is **frozen**: same 30 tasks, same scoring logic, same model for both.

---

## Directory layout

```
research/smollm2/
├── README.md             ← you are here
├── baseline/             ← frozen comparator records
├── experiments/          ← per-experiment records (EXP-NNN.md)
├── runs/                 ← machine-readable run manifests
├── analysis/             ← failure taxonomy, bottleneck analysis
├── reproducibility/      ← exact reproduction commands
└── figures/              ← (reserved for charts)
```

Benchmark artifacts (raw JSON, per-turn interactions) live in
`benchmarks/baseline/`, `benchmarks/idos/`, and `benchmarks/results/`.
The `research/` tree links to and summarises those artifacts.

---

## Experimental progression

```
Bare SmolLM2-360M baseline:  37% (11/30)   ← frozen comparator
                                             ← NOT a ratchet starting point

IDOS ratchet (measured improvement over prior IDOS state):
  EXP-001  bootstrap  IDOS first run → 17% (5/30)
  EXP-002  KEEP       17% → 30%
  EXP-003  KEEP       30% → 50%
  EXP-009  KEEP       50% → 67%
  EXP-019  KEEP       67% → 70%
  EXP-020  KEEP       70% → 73%
  EXP-026  KEEP       73% → 77%   ← current proven tip
```

The early IDOS steps (17%, 30%) are *below* the bare baseline. IDOS first exceeded
the bare baseline between EXP-009 (67%) and EXP-003 context. The 40 pp gap is only
meaningful at the proven 77% tip vs the frozen 37% bare.

---

## What is frozen / what can change

| Frozen (must not change) | Allowed to change |
|--------------------------|-------------------|
| `benchmarks/tasks/v0.1.0.json` | `adapters/openai_adapter.py` |
| `benchmarks/scoring.py` | `core/` modules |
| `benchmarks/runner.py` | `runtime/orchestrator.py` |
| `benchmarks/ratchet.py` | `tests/` |
| Model (`smollm2:360m-instruct-q4_0`) | System prompts / tool scaffolding |
| Bare baseline results | Memory / profile recall logic |

---

## Reproduction

See `research/smollm2/reproducibility/REPRODUCE.md` for exact commands.
