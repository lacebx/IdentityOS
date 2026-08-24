# Run idos-20260821T080902Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T08:31:17.081621+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `43.9568s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 54.5248s |
| memory | 4/5 (80%) | 0/5 (0%) | 75.7769s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.4519s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 22.6332s |
| tools | 2/5 (40%) | 0/5 (0%) | 63.3201s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0337s |

## Tasks

- `A01` [reasoning] **PASS** (29.1801s) 
- `A02` [reasoning] **PASS** (20.4226s) 
- `A03` [reasoning] **FAIL** (21.8786s) 
- `A04` [reasoning] **PASS** (15.0983s) 
- `A05` [reasoning] **FAIL** (26.5865s) 
- `B01` [memory] **PASS** (32.0709s) 
- `B02` [memory] **PASS** (65.8119s) 
- `B03` [memory] **PASS** (56.6368s) 
- `B04` [memory] **FAIL** (165.0716s) 
- `B05` [memory] **PASS** (59.2934s) 
- `C01` [tools] **FAIL** (55.1541s) 
- `C02` [tools] **FAIL** (95.8606s) 
- `C03` [tools] **FAIL** (54.6151s) 
- `C04` [tools] **PASS** (54.1571s) 
- `C05` [tools] **PASS** (56.8138s) 
- `D01` [persistence] **PASS** (50.7291s) restart_after_setup
- `D02` [persistence] **PASS** (43.3298s) restart_after_setup
- `D03` [persistence] **PASS** (51.7135s) restart_after_setup
- `D04` [persistence] **FAIL** (45.3578s) restart_after_setup
- `D05` [persistence] **PASS** (46.1295s) restart_after_setup
- `E01` [long_task] **FAIL** (50.9969s) 
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **PASS** (55.6717s) 
- `E05` [long_task] **FAIL** (165.9552s) 
- `F01` [truthfulness] **PASS** (0.0082s) 
- `F02` [truthfulness] **PASS** (0.1117s) 
- `F03` [truthfulness] **PASS** (0.0278s) 
- `F04` [truthfulness] **PASS** (0.012s) 
- `F05` [truthfulness] **PASS** (0.0086s) 
