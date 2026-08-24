# Mode B environment constraints

## Host

| Field | Value |
|-------|-------|
| Hostname | DESKTOP-RNM |
| OS | WSL2 Linux |
| RAM | 3.7 GiB |
| Swap | 1.0 GiB |
| CPU | Intel i5-10210U (CPU-only Ollama) |

## Concurrent Mode A / Mode B limitation

**Observed:** Running Mode A (SmolLM2 autopilot/ratchet) and Mode B (4B-class models)
concurrently on this host is not viable.

Evidence:
- Host RAM is ~3.7 GiB.
- `qwen3:4b` alone is ~2.5 GB on disk / large in-memory footprint.
- `gemma3:4b` is ~3.3 GB on disk.
- While Mode A held SmolLM2 loaded, available RAM dropped below ~100 MiB and swap filled.
- An Ollama crash during Mode A EXP-051 coincided with extreme memory pressure
  (`Connection error` in the autopilot log).

**Operational rule for this machine:**
Mode B baselines and IDOS runs must wait until Mode A is not holding an active
`benchmarks/ratchet.py` Ollama suite.

Scripts:
- `scripts/mode_b_overnight.sh` waits for Mode A ratchet release before each model phase.
