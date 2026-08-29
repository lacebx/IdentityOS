# Mode B protocol

## Frozen benchmark

Mode B uses the same frozen benchmark as Mode A:

- tasks: `benchmarks/tasks/v0.1.0.json`
- runner: `benchmarks/runner.py`
- scoring: `benchmarks/scoring.py`

No task, scoring, ordering, or expected-output changes are allowed unless a benchmark
bug is demonstrated and documented first.

## Comparison design

For each tested model:

1. Pull and verify the Ollama model.
2. Record model metadata and a trivial inference smoke test.
3. Run the full benchmark in `bare` mode.
4. Preserve the full run artifact as the frozen bare comparator for that model.
5. Run the full benchmark in `idos` mode from the same commit.
6. Preserve the full run artifact.
7. Compare:
   - total score
   - category scores
   - task-level outcomes
   - hallucinations
   - latency
   - persistence behavior
   - tool behavior

## Interpretation rules

Separate:

- **Observed**: what the artifact literally shows
- **Inference**: what the evidence suggests
- **Hypothesis**: what should be tested next

Do not collapse these together.

## Initial model sample

- `qwen3:4b`
- `gemma3:4b`
- `phi4-mini`
