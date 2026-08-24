# Run idos-20260821T164236Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T16:54:05.529032+00:00`
- tasks completed: `16`
- success: `12/16` (75%)
- hallucination: `0/16` (0%)
- avg latency: `43.0324s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 4/5 (80%) | 0/5 (0%) | 63.5093s |
| persistence | 1/1 (100%) | 0/1 (0%) | 43.9494s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 17.8471s |
| tools | 3/5 (60%) | 0/5 (0%) | 47.5575s |

## Tasks

- `A01` [reasoning] **PASS** (29.9562s) 
- `A02` [reasoning] **PASS** (13.665s) 
- `A03` [reasoning] **PASS** (12.944s) 
- `A04` [reasoning] **PASS** (12.4803s) 
- `A05` [reasoning] **FAIL** (20.1901s) 
- `B01` [memory] **PASS** (46.6555s) 
- `B02` [memory] **PASS** (44.7683s) 
- `B03` [memory] **PASS** (46.5886s) 
- `B04` [memory] **FAIL** (133.7609s) 
- `B05` [memory] **PASS** (45.7731s) 
- `C01` [tools] **FAIL** (41.7859s) 
- `C02` [tools] **FAIL** (52.5932s) 
- `C03` [tools] **PASS** (56.8666s) 
- `C04` [tools] **PASS** (41.8873s) 
- `C05` [tools] **PASS** (44.6545s) 
- `D01` [persistence] **PASS** (43.9494s) restart_after_setup
