# Mode B — Cross-model validation

Mode B tests whether the existing IdentityOS runtime improves multiple small local
models relative to each model's own bare baseline on the same frozen 30-task benchmark.

## Research question

Does IdentityOS provide measurable augmentation benefits across multiple small/local
models, or were the SmolLM2 gains primarily model-specific?

## Initial model set

- `qwen3:4b`
- `gemma3:4b`
- `phi4-mini`

## Rules

- Keep the benchmark fixed.
- Compare each model against its own bare baseline.
- Record task-level evidence, not just totals.
- Treat regressions and inconclusive results as valid research outcomes.
- Keep Mode B artifacts separate from the active SmolLM2 line.

## Status

Mode B was initialized from the proven SmolLM2 KEEP commit `e1cb45c` in an isolated
worktree so the active SmolLM2 autopilot remains untouched.

Model pulls, bare baselines, and first IDOS comparisons are recorded under:

- `research/mode-b/models/`
- `research/mode-b/baselines/`
- `research/mode-b/idos/`
- `research/mode-b/manifests/`
- `research/mode-b/analysis/`
