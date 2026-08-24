# Run idos-20260821T145959Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T15:20:12.539336+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `40.4091s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 68.8476s |
| memory | 4/5 (80%) | 0/5 (0%) | 58.0068s |
| persistence | 4/5 (80%) | 0/5 (0%) | 56.1272s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 16.962s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.5041s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0068s |

## Tasks

- `A01` [reasoning] **PASS** (30.6825s) 
- `A02` [reasoning] **PASS** (11.8061s) 
- `A03` [reasoning] **FAIL** (13.9747s) 
- `A04` [reasoning] **PASS** (13.7571s) 
- `A05` [reasoning] **FAIL** (14.5895s) 
- `B01` [memory] **PASS** (22.3126s) 
- `B02` [memory] **PASS** (43.1343s) 
- `B03` [memory] **PASS** (42.2801s) 
- `B04` [memory] **FAIL** (139.5707s) 
- `B05` [memory] **PASS** (42.7365s) 
- `C01` [tools] **FAIL** (42.647s) 
- `C02` [tools] **FAIL** (44.4477s) 
- `C03` [tools] **PASS** (42.1381s) 
- `C04` [tools] **FAIL** (40.5461s) 
- `C05` [tools] **FAIL** (42.7415s) 
- `D01` [persistence] **PASS** (44.8974s) restart_after_setup
- `D02` [persistence] **PASS** (103.7972s) restart_after_setup
- `D03` [persistence] **PASS** (43.2811s) restart_after_setup
- `D04` [persistence] **FAIL** (43.8663s) restart_after_setup
- `D05` [persistence] **PASS** (44.7938s) restart_after_setup
- `E01` [long_task] **FAIL** (45.7264s) 
- `E02` [long_task] **FAIL** (45.9259s) 
- `E03` [long_task] **PASS** (99.5187s) 
- `E04` [long_task] **PASS** (54.5212s) 
- `E05` [long_task] **FAIL** (98.5459s) 
- `F01` [truthfulness] **PASS** (0.0071s) 
- `F02` [truthfulness] **PASS** (0.0068s) 
- `F03` [truthfulness] **PASS** (0.0071s) 
- `F04` [truthfulness] **PASS** (0.0065s) 
- `F05` [truthfulness] **PASS** (0.0065s) 
