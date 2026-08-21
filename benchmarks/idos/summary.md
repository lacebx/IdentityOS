# Run idos-20260821T104042Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T11:01:17.430371+00:00`
- tasks completed: `30`
- success: `22/30` (73%)
- hallucination: `0/30` (0%)
- avg latency: `41.1429s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 69.5907s |
| memory | 5/5 (100%) | 0/5 (0%) | 64.6262s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.6791s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.7867s |
| tools | 2/5 (40%) | 0/5 (0%) | 51.1424s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0323s |

## Tasks

- `A01` [reasoning] **PASS** (28.0926s) 
- `A02` [reasoning] **PASS** (12.2472s) 
- `A03` [reasoning] **PASS** (10.9545s) 
- `A04` [reasoning] **PASS** (12.0511s) 
- `A05` [reasoning] **FAIL** (15.588s) 
- `B01` [memory] **PASS** (61.1625s) 
- `B02` [memory] **PASS** (41.1483s) 
- `B03` [memory] **PASS** (42.5353s) 
- `B04` [memory] **PASS** (135.2137s) 
- `B05` [memory] **PASS** (43.0713s) 
- `C01` [tools] **FAIL** (44.3779s) 
- `C02` [tools] **FAIL** (81.7819s) 
- `C03` [tools] **FAIL** (42.7261s) 
- `C04` [tools] **PASS** (41.4024s) 
- `C05` [tools] **PASS** (45.4236s) 
- `D01` [persistence] **PASS** (47.5777s) restart_after_setup
- `D02` [persistence] **PASS** (46.2873s) restart_after_setup
- `D03` [persistence] **PASS** (44.3775s) restart_after_setup
- `D04` [persistence] **FAIL** (45.7607s) restart_after_setup
- `D05` [persistence] **PASS** (44.3923s) restart_after_setup
- `E01` [long_task] **FAIL** (47.3542s) 
- `E02` [long_task] **FAIL** (49.5837s) 
- `E03` [long_task] **FAIL** (90.7955s) 
- `E04` [long_task] **PASS** (54.7466s) 
- `E05` [long_task] **PASS** (105.4733s) 
- `F01` [truthfulness] **PASS** (0.0085s) 
- `F02` [truthfulness] **PASS** (0.0074s) 
- `F03` [truthfulness] **PASS** (0.054s) 
- `F04` [truthfulness] **PASS** (0.062s) 
- `F05` [truthfulness] **PASS** (0.0297s) 
