# IDOS Baseline v0.1.0

Model: `smollm2:360m-instruct-q4_0`

Numbers below are measured, not assumed. Empty cells mean that mode has not been run yet.

| Metric | Bare | IDOS |
|---|---|---|
| Task Success | 37% (11/30) | 67% (20/30) |
| Hallucination | 7% (2/30) | 0% (0/30) |
| Avg Latency | 2.0249s | 37.6975s |

## By category

| Category | Bare success | IDOS success | Bare hallucination | IDOS hallucination |
|---|---|---|---|---|
| long_task | 20% (1/5) | 20% (1/5) | 0% (0/5) | 0% (0/5) |
| memory | 60% (3/5) | 100% (5/5) | 0% (0/5) | 0% (0/5) |
| persistence | 0% (0/5) | 80% (4/5) | 0% (0/5) | 0% (0/5) |
| reasoning | 40% (2/5) | 80% (4/5) | 0% (0/5) | 0% (0/5) |
| tools | 40% (2/5) | 20% (1/5) | 0% (0/5) | 0% (0/5) |
| truthfulness | 60% (3/5) | 100% (5/5) | 40% (2/5) | 0% (0/5) |

## What this is

Control: the same local model, same machine, same tasks, no IdentityOS.
Treatment: IdentityOS identity + memory + capabilities + persistence + orchestration.

Do not edit these numbers by hand. Re-run `python benchmarks/runner.py`.
