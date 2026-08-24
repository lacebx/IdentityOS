# Run idos-20260821T175246Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T18:24:51.649323+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `64.1307s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 213.2936s |
| memory | 5/5 (100%) | 0/5 (0%) | 58.4679s |
| persistence | 4/5 (80%) | 0/5 (0%) | 49.5748s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.8653s |
| tools | 1/5 (20%) | 0/5 (0%) | 47.5766s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0061s |

## Tasks

- `A01` [reasoning] **PASS** (29.1081s) 
- `A02` [reasoning] **PASS** (12.7588s) 
- `A03` [reasoning] **PASS** (10.8732s) 
- `A04` [reasoning] **PASS** (12.5231s) 
- `A05` [reasoning] **FAIL** (14.0634s) 
- `B01` [memory] **PASS** (24.3892s) 
- `B02` [memory] **PASS** (27.7394s) 
- `B03` [memory] **PASS** (43.8278s) 
- `B04` [memory] **PASS** (153.8391s) 
- `B05` [memory] **PASS** (42.5441s) 
- `C01` [tools] **FAIL** (42.0478s) 
- `C02` [tools] **FAIL** (51.1916s) 
- `C03` [tools] **PASS** (48.5996s) 
- `C04` [tools] **FAIL** (46.0139s) 
- `C05` [tools] **FAIL** (50.0301s) 
- `D01` [persistence] **PASS** (52.0907s) restart_after_setup
- `D02` [persistence] **PASS** (48.5925s) restart_after_setup
- `D03` [persistence] **PASS** (56.5142s) restart_after_setup
- `D04` [persistence] **FAIL** (44.2186s) restart_after_setup
- `D05` [persistence] **PASS** (46.4581s) restart_after_setup
- `E01` [long_task] **FAIL** (787.7281s) 
- `E02` [long_task] **FAIL** (43.9723s) 
- `E03` [long_task] **PASS** (90.2606s) 
- `E04` [long_task] **PASS** (49.5403s) 
- `E05` [long_task] **FAIL** (94.9668s) 
- `F01` [truthfulness] **PASS** (0.0051s) 
- `F02` [truthfulness] **PASS** (0.0062s) 
- `F03` [truthfulness] **PASS** (0.0062s) 
- `F04` [truthfulness] **PASS** (0.0059s) 
- `F05` [truthfulness] **PASS** (0.0071s) 
