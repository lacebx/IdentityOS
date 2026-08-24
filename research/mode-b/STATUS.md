# Mode B status log

## 2026-08-24T17:30Z (approx)

### Completed
- Isolated worktree at proven KEEP `e1cb45c`: `/home/lace/Desktop/identity-runtime-mode-b`
- Branch: `mode-b/cross-model-validation`
- Research archive skeleton under `research/mode-b/`
- Scripts: `mode_b_runner.py`, `mode_b_report.py`, `mode_b_overnight.sh`
- Model pull: `qwen3:4b` SUCCESS (4.0B, Q4_K_M, 2.5 GB)

### In progress / blocked
- Mode A SmolLM2 autopilot still active (`EXP-051` ratchet).
- Host has only ~3.7 GiB RAM. Concurrent Mode A + Mode B crashes Ollama.
- `gemma3:4b` pull started then stopped to avoid fighting Mode A for Ollama.
- `phi4-mini` not yet pulled.
- Bare baselines and IDOS runs not yet started (blocked on Mode A releasing Ollama).

### Autonomous continuation
- `scripts/mode_b_overnight.sh` is running (PID in `/tmp/mode_b_overnight.pid`).
- It waits for Mode A `benchmarks/ratchet.py` to be idle ~90s, then runs
  smoke + bare + IDOS for each available model.
- Log: `/tmp/mode_b_overnight.log`
- Commit: `e25dccc` on branch `mode-b/cross-model-validation`

### Hard blocker for full Mode B evidence on this host
A full `qwen3:4b` bare+IDOS suite needs exclusive Ollama for hours.
Mode A currently restarts ratchets frequently. On 3.7 GiB RAM, concurrent
Mode A + Mode B previously crashed Ollama.

If Mode A never stays idle long enough, Mode B will remain waiting.
Recommended when you return: pause Mode A overnight, let Mode B finish
baselines, then resume Mode A — or move Mode B to a larger machine.
