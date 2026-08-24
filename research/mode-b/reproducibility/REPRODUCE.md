# Mode B reproducibility

Mode B runs from the proven SmolLM2 KEEP commit:

```bash
git checkout e1cb45c
```

An isolated worktree was used so Mode B does not interfere with the active SmolLM2
autopilot working tree.

## Pull target models

```bash
ollama pull qwen3:4b
ollama pull gemma3:4b
ollama pull phi4-mini
ollama list
```

## Run a model's smoke test, bare baseline, and IDOS comparison

```bash
python scripts/mode_b_runner.py --model qwen3:4b --slug qwen3-4b --phase both
python scripts/mode_b_runner.py --model gemma3:4b --slug gemma3-4b --phase both
python scripts/mode_b_runner.py --model phi4-mini --slug phi4-mini --phase both
```

## Regenerate the comparison report

```bash
python scripts/mode_b_report.py
```
