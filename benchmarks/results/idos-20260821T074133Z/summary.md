# Run idos-20260821T074133Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T08:08:13.151485+00:00`
- tasks completed: `30`
- success: `18/30` (60%)
- hallucination: `0/30` (0%)
- avg latency: `53.3212s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 73.3676s |
| memory | 4/5 (80%) | 0/5 (0%) | 83.6252s |
| persistence | 4/5 (80%) | 0/5 (0%) | 65.3012s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 29.4126s |
| tools | 1/5 (20%) | 0/5 (0%) | 68.2124s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0082s |

## Tasks

- `A01` [reasoning] **FAIL** (63.8805s) 
- `A02` [reasoning] **PASS** (23.5191s) 
- `A03` [reasoning] **FAIL** (17.6936s) 
- `A04` [reasoning] **PASS** (19.4064s) 
- `A05` [reasoning] **FAIL** (22.5633s) 
- `B01` [memory] **PASS** (39.6842s) 
- `B02` [memory] **PASS** (60.819s) 
- `B03` [memory] **PASS** (68.3273s) 
- `B04` [memory] **FAIL** (187.5993s) 
- `B05` [memory] **PASS** (61.6963s) 
- `C01` [tools] **FAIL** (70.1135s) 
- `C02` [tools] **FAIL** (67.7551s) 
- `C03` [tools] **FAIL** (69.335s) 
- `C04` [tools] **PASS** (58.6674s) 
- `C05` [tools] **FAIL** (75.191s) 
- `D01` [persistence] **PASS** (64.0196s) restart_after_setup
- `D02` [persistence] **PASS** (66.0763s) restart_after_setup
- `D03` [persistence] **PASS** (63.3902s) restart_after_setup
- `D04` [persistence] **FAIL** (63.0712s) restart_after_setup
- `D05` [persistence] **PASS** (69.9489s) restart_after_setup
- `E01` [long_task] **FAIL** (54.0119s) 
- `E02` [long_task] **FAIL** (48.049s) 
- `E03` [long_task] **PASS** (94.3774s) 
- `E04` [long_task] **PASS** (70.1095s) 
- `E05` [long_task] **FAIL** (100.29s) 
- `F01` [truthfulness] **PASS** (0.0082s) 
- `F02` [truthfulness] **PASS** (0.0074s) 
- `F03` [truthfulness] **PASS** (0.0087s) 
- `F04` [truthfulness] **PASS** (0.0065s) 
- `F05` [truthfulness] **PASS** (0.0103s) 
