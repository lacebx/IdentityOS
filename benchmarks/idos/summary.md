# Run idos-20260821T134659Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T14:05:59.457157+00:00`
- tasks completed: `30`
- success: `23/30` (77%)
- hallucination: `0/30` (0%)
- avg latency: `38.0028s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 68.3736s |
| memory | 5/5 (100%) | 0/5 (0%) | 57.4232s |
| persistence | 4/5 (80%) | 0/5 (0%) | 43.4727s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.9635s |
| tools | 3/5 (60%) | 0/5 (0%) | 42.7743s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0097s |

## Tasks

- `A01` [reasoning] **PASS** (31.3283s) 
- `A02` [reasoning] **PASS** (11.7432s) 
- `A03` [reasoning] **PASS** (10.5346s) 
- `A04` [reasoning] **PASS** (11.8765s) 
- `A05` [reasoning] **FAIL** (14.335s) 
- `B01` [memory] **PASS** (24.7773s) 
- `B02` [memory] **PASS** (40.5855s) 
- `B03` [memory] **PASS** (42.0898s) 
- `B04` [memory] **PASS** (130.8635s) 
- `B05` [memory] **PASS** (48.8s) 
- `C01` [tools] **FAIL** (40.7818s) 
- `C02` [tools] **FAIL** (48.3308s) 
- `C03` [tools] **PASS** (41.5117s) 
- `C04` [tools] **PASS** (41.4617s) 
- `C05` [tools] **PASS** (41.7856s) 
- `D01` [persistence] **PASS** (41.4802s) restart_after_setup
- `D02` [persistence] **PASS** (46.0838s) restart_after_setup
- `D03` [persistence] **PASS** (45.4293s) restart_after_setup
- `D04` [persistence] **FAIL** (42.1718s) restart_after_setup
- `D05` [persistence] **PASS** (42.1983s) restart_after_setup
- `E01` [long_task] **FAIL** (49.2411s) 
- `E02` [long_task] **FAIL** (44.4877s) 
- `E03` [long_task] **FAIL** (95.8995s) 
- `E04` [long_task] **PASS** (64.4631s) 
- `E05` [long_task] **PASS** (87.7766s) 
- `F01` [truthfulness] **PASS** (0.0106s) 
- `F02` [truthfulness] **PASS** (0.0093s) 
- `F03` [truthfulness] **PASS** (0.0096s) 
- `F04` [truthfulness] **PASS** (0.0081s) 
- `F05` [truthfulness] **PASS** (0.0109s) 
