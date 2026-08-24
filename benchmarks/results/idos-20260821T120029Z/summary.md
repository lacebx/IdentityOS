# Run idos-20260821T120029Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T12:19:58.130147+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `38.935s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 68.6588s |
| memory | 5/5 (100%) | 0/5 (0%) | 58.9054s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.4212s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 18.528s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.09s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0068s |

## Tasks

- `A01` [reasoning] **PASS** (28.8049s) 
- `A02` [reasoning] **PASS** (12.4365s) 
- `A03` [reasoning] **PASS** (10.829s) 
- `A04` [reasoning] **PASS** (24.2424s) 
- `A05` [reasoning] **FAIL** (16.327s) 
- `B01` [memory] **PASS** (27.9972s) 
- `B02` [memory] **PASS** (42.3083s) 
- `B03` [memory] **PASS** (46.0286s) 
- `B04` [memory] **PASS** (132.7967s) 
- `B05` [memory] **PASS** (45.396s) 
- `C01` [tools] **FAIL** (41.2431s) 
- `C02` [tools] **FAIL** (41.7488s) 
- `C03` [tools] **PASS** (43.3697s) 
- `C04` [tools] **FAIL** (42.8602s) 
- `C05` [tools] **FAIL** (41.228s) 
- `D01` [persistence] **PASS** (43.5846s) restart_after_setup
- `D02` [persistence] **PASS** (45.595s) restart_after_setup
- `D03` [persistence] **PASS** (42.864s) restart_after_setup
- `D04` [persistence] **FAIL** (44.6777s) restart_after_setup
- `D05` [persistence] **PASS** (50.3847s) restart_after_setup
- `E01` [long_task] **FAIL** (52.1965s) 
- `E02` [long_task] **FAIL** (48.1372s) 
- `E03` [long_task] **FAIL** (93.0892s) 
- `E04` [long_task] **PASS** (49.7679s) 
- `E05` [long_task] **FAIL** (100.1034s) 
- `F01` [truthfulness] **PASS** (0.0077s) 
- `F02` [truthfulness] **PASS** (0.0083s) 
- `F03` [truthfulness] **PASS** (0.0057s) 
- `F04` [truthfulness] **PASS** (0.0065s) 
- `F05` [truthfulness] **PASS** (0.0059s) 
