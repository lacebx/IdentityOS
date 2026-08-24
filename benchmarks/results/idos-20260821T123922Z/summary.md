# Run idos-20260821T123922Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T12:59:21.931686+00:00`
- tasks completed: `30`
- success: `22/30` (73%)
- hallucination: `0/30` (0%)
- avg latency: `39.9824s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 69.4331s |
| memory | 5/5 (100%) | 0/5 (0%) | 63.6124s |
| persistence | 4/5 (80%) | 0/5 (0%) | 46.7976s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.3225s |
| tools | 3/5 (60%) | 0/5 (0%) | 44.7197s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0093s |

## Tasks

- `A01` [reasoning] **PASS** (24.2132s) 
- `A02` [reasoning] **PASS** (14.9803s) 
- `A03` [reasoning] **PASS** (10.9368s) 
- `A04` [reasoning] **PASS** (11.5322s) 
- `A05` [reasoning] **FAIL** (14.95s) 
- `B01` [memory] **PASS** (21.5709s) 
- `B02` [memory] **PASS** (25.5894s) 
- `B03` [memory] **PASS** (48.1434s) 
- `B04` [memory] **PASS** (160.4948s) 
- `B05` [memory] **PASS** (62.2637s) 
- `C01` [tools] **FAIL** (50.4012s) 
- `C02` [tools] **FAIL** (45.6623s) 
- `C03` [tools] **PASS** (41.6256s) 
- `C04` [tools] **PASS** (44.3289s) 
- `C05` [tools] **PASS** (41.5803s) 
- `D01` [persistence] **PASS** (45.3107s) restart_after_setup
- `D02` [persistence] **PASS** (44.3688s) restart_after_setup
- `D03` [persistence] **PASS** (46.1778s) restart_after_setup
- `D04` [persistence] **FAIL** (45.8358s) restart_after_setup
- `D05` [persistence] **PASS** (52.2949s) restart_after_setup
- `E01` [long_task] **FAIL** (47.1236s) 
- `E02` [long_task] **FAIL** (44.7597s) 
- `E03` [long_task] **FAIL** (90.0198s) 
- `E04` [long_task] **PASS** (77.6081s) 
- `E05` [long_task] **FAIL** (87.6545s) 
- `F01` [truthfulness] **PASS** (0.006s) 
- `F02` [truthfulness] **PASS** (0.0068s) 
- `F03` [truthfulness] **PASS** (0.0166s) 
- `F04` [truthfulness] **PASS** (0.0058s) 
- `F05` [truthfulness] **PASS** (0.0113s) 
