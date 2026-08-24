# Run idos-20260821T173220Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T17:51:34.597976+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `38.471s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 70.4818s |
| memory | 5/5 (100%) | 0/5 (0%) | 55.6134s |
| persistence | 4/5 (80%) | 0/5 (0%) | 44.4252s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 16.7595s |
| tools | 1/5 (20%) | 0/5 (0%) | 43.5388s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0071s |

## Tasks

- `A01` [reasoning] **PASS** (29.3329s) 
- `A02` [reasoning] **PASS** (13.6307s) 
- `A03` [reasoning] **PASS** (14.0778s) 
- `A04` [reasoning] **PASS** (13.2297s) 
- `A05` [reasoning] **FAIL** (13.5264s) 
- `B01` [memory] **PASS** (22.1021s) 
- `B02` [memory] **PASS** (28.3846s) 
- `B03` [memory] **PASS** (45.5969s) 
- `B04` [memory] **PASS** (140.9192s) 
- `B05` [memory] **PASS** (41.0644s) 
- `C01` [tools] **FAIL** (40.7461s) 
- `C02` [tools] **FAIL** (45.476s) 
- `C03` [tools] **FAIL** (49.1621s) 
- `C04` [tools] **PASS** (41.4755s) 
- `C05` [tools] **FAIL** (40.8345s) 
- `D01` [persistence] **PASS** (44.8498s) restart_after_setup
- `D02` [persistence] **PASS** (47.1597s) restart_after_setup
- `D03` [persistence] **PASS** (44.6392s) restart_after_setup
- `D04` [persistence] **FAIL** (43.9363s) restart_after_setup
- `D05` [persistence] **PASS** (41.541s) restart_after_setup
- `E01` [long_task] **FAIL** (44.0098s) 
- `E02` [long_task] **FAIL** (41.412s) 
- `E03` [long_task] **PASS** (91.942s) 
- `E04` [long_task] **PASS** (66.7028s) 
- `E05` [long_task] **FAIL** (108.3424s) 
- `F01` [truthfulness] **PASS** (0.0065s) 
- `F02` [truthfulness] **PASS** (0.0075s) 
- `F03` [truthfulness] **PASS** (0.0059s) 
- `F04` [truthfulness] **PASS** (0.0071s) 
- `F05` [truthfulness] **PASS** (0.0084s) 
