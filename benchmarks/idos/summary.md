# Run idos-20260820T012051Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-20T01:39:42.633064+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `37.6975s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 62.0148s |
| memory | 5/5 (100%) | 0/5 (0%) | 59.1359s |
| persistence | 4/5 (80%) | 0/5 (0%) | 42.2706s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.4925s |
| tools | 1/5 (20%) | 0/5 (0%) | 47.2649s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0063s |

## Tasks

- `A01` [reasoning] **PASS** (26.6391s) 
- `A02` [reasoning] **PASS** (10.8336s) 
- `A03` [reasoning] **PASS** (9.709s) 
- `A04` [reasoning] **PASS** (11.1414s) 
- `A05` [reasoning] **FAIL** (19.1396s) 
- `B01` [memory] **PASS** (26.1029s) 
- `B02` [memory] **PASS** (40.3456s) 
- `B03` [memory] **PASS** (58.0884s) 
- `B04` [memory] **PASS** (128.5322s) 
- `B05` [memory] **PASS** (42.6103s) 
- `C01` [tools] **FAIL** (40.9471s) 
- `C02` [tools] **FAIL** (69.9272s) 
- `C03` [tools] **FAIL** (39.9707s) 
- `C04` [tools] **PASS** (39.4549s) 
- `C05` [tools] **FAIL** (46.0244s) 
- `D01` [persistence] **PASS** (47.6596s) restart_after_setup
- `D02` [persistence] **PASS** (44.1606s) restart_after_setup
- `D03` [persistence] **PASS** (42.6343s) restart_after_setup
- `D04` [persistence] **FAIL** (38.4471s) restart_after_setup
- `D05` [persistence] **PASS** (38.4512s) restart_after_setup
- `E01` [long_task] **FAIL** (40.3063s) 
- `E02` [long_task] **FAIL** (43.1323s) 
- `E03` [long_task] **FAIL** (89.9604s) 
- `E04` [long_task] **PASS** (48.5264s) 
- `E05` [long_task] **FAIL** (88.1487s) 
- `F01` [truthfulness] **PASS** (0.0087s) 
- `F02` [truthfulness] **PASS** (0.0056s) 
- `F03` [truthfulness] **PASS** (0.0056s) 
- `F04` [truthfulness] **PASS** (0.0054s) 
- `F05` [truthfulness] **PASS** (0.0061s) 
