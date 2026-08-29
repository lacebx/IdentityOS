# Mode B status

## 2026-08-25T04:10Z (approx) — prior run audit + restart

### What happened in the previous Mode B attempt

Process is **stopped**. No exclusive PID/log remained in `/tmp`.

Recovered evidence:

1. **qwen3:4b smoke #1** (`20260824T200825Z`) — PASS, latency **597s** (cold load + thinking).
2. **qwen3:4b smoke #2** (`20260824T201823Z`) — PASS, latency **43s**.
3. **qwen3:4b bare** (`bare-20260824T201908Z`) — **incomplete**, stopped after 3/30 tasks:
   - A01 PASS (31.8s)
   - A02 FAIL — Ollama timed out
   - A03 PASS (468.9s)
   - No further tasks; no IDOS run; no done marker

**Observed cause:** with default Qwen3 thinking enabled, single tasks approached/exceeded the prior 600s timeout and the exclusive process died before finishing the suite (likely host sleep/OOM/kill; `/tmp` log was lost).

### Restart configuration changes

- Bare/IDOS timeout raised to **1200s**
- Native Ollama bare calls set **`think: false`** (documented Mode B config)
- IDOS `OllamaAdapter` uses `think=False`, `temperature=0.0`, same timeout
- Durable log also written to `research/mode-b/runs/exclusive.log`

### Models ready

- `qwen3:4b`
- `gemma3:4b`
- `phi4-mini` / `phi4-mini:latest`

### Monitor

```bash
tail -f /tmp/mode_b_exclusive.log
# or
tail -f /home/lace/Desktop/identity-runtime-mode-b/research/mode-b/runs/exclusive.log
ps -p $(cat /tmp/mode_b_exclusive.pid) -o pid,etime,cmd
ls -lt research/mode-b/manifests/
```
