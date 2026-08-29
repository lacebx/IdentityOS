# Cross-model results

| Model | Bare | IDOS | Δ tasks | Hallucinations Bare | Hallucinations IDOS | Avg latency Bare | Avg latency IDOS |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemma3-4b | 21/30 | 26/30 | +5 | 0/30 | 0/30 | 12.8897s | 290.9214s |
| phi4-mini | 21/30 | 25/30 | +4 | 0/30 | 0/30 | 10.8335s | 224.8122s |
| qwen3-4b | 22/30 | 18/30 | -4 | 0/30 | 0/30 | 405.0059s | 779.386s |

## Failure matrix

| Task | Category | gemma3-4b | phi4-mini | qwen3-4b |
|---|---|---|---|---|
| A05 | reasoning | FAIL | FAIL | FAIL |
| C01 | tools | FAIL | FAIL | PASS |
| C02 | tools | FAIL | FAIL | FAIL |
| D04 | persistence | FAIL | FAIL | FAIL |
| E01 | long_task | PASS | PASS | FAIL |
| E02 | long_task | PASS | PASS | FAIL |
| E03 | long_task | PASS | PASS | FAIL |
