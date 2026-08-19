# Benchmarks

Frozen comparison: **the same tiny local model, bare vs IdentityOS**.

This is not IdentityBench (the long-running identity observability suite).
This directory answers one question:

> Can IdentityOS make SmolLM2-360M substantially more useful than the same
> model running without identity, memory, tools, or persistence?

## Run

```bash
# Control
python benchmarks/runner.py --mode bare --freeze

# Treatment (same model, same tasks)
python benchmarks/runner.py --mode idos --freeze --reset-identity

# Or both, then rebuild the report
python benchmarks/runner.py --mode both --freeze --reset-identity
python benchmarks/runner.py --report-only
```

Useful flags:

```bash
python benchmarks/runner.py --mode bare --task A01
python benchmarks/runner.py --mode idos --category memory
python benchmarks/runner.py --mode both --limit 3
python benchmarks/runner.py --mode both --demo --reset-identity
```

Default model: `smollm2:360m-instruct-q4_0`.

## Layout

```text
benchmarks/
├── tasks/v0.1.0.json     frozen task suite
├── runner.py             one command reproduces the experiment
├── baseline/             Bare Baseline v0.1.0 (after --freeze)
├── idos/                 IDOS v0.1.0 (after --freeze)
├── results/<run-id>/     every interaction, JSON + Markdown
├── reports/              comparison tables
└── experiments/          IDOS Ratchet records (EXP-001, …)
```

After every prompt, the runner writes:

```text
results/<run-id>/interactions/NNN_<task>_<mode>_tN.json
results/<run-id>/interactions/NNN_<task>_<mode>_tN.md
results/<run-id>/results.json
results/<run-id>/summary.md
```

Those files are evidence. Model claims are not.

## Rules

1. Do not change `tasks/v0.1.0.json` after Bare Baseline v0.1.0 is frozen.
2. A later task change is **BENCHMARK v0.2.0**.
3. Do not tune IdentityOS to pass these tasks before the first IDOS run.
4. One improvement per experiment (`experiments/EXP-NNN.md`), then re-run.
5. Keep the change only if the measured score improves without hiding failures.

## Ratchet

The model and `tasks/v0.1.0.json` are locked. A runtime change stays only if the
frozen IDOS suite gets strictly better.

```bash
# First IDOS measurement (once)
git checkout -b ratchet/smollm-v0.1
python benchmarks/ratchet.py --bootstrap --hypothesis "First IDOS baseline on SmolLM2-360M"

# Each later experiment: implement ONE runtime change, then
python benchmarks/ratchet.py --exp EXP-001 --hypothesis "Wire Ollama native tool calls" --change "adapters/openai_adapter.py" --push
```

KEEP commits on the current branch (refuses `main` / `master`) and can `--push`.
REVERT restores allowlisted runtime files to HEAD and writes `experiments/EXP-NNN.md`.

Judge gates: full 30-task suite, same model, success rate up, hallucination not
up, latency ≤ 1.25× previous, no category drop of more than one successful task,
pytest green, exam hashes unchanged.

`--decide-only --before … --after …` judges two result files without calling the model.

Methodology: [`docs/BENCHMARK.md`](../docs/BENCHMARK.md)
