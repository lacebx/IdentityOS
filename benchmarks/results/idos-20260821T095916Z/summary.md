# Run idos-20260821T095916Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T10:18:33.277413+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `38.5462s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 64.1622s |
| memory | 5/5 (100%) | 0/5 (0%) | 59.7188s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.0403s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 15.5884s |
| tools | 3/5 (60%) | 0/5 (0%) | 46.7609s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0068s |

## Tasks

- `A01` [reasoning] **FAIL** (26.1396s) 
- `A02` [reasoning] **PASS** (12.8643s) 
- `A03` [reasoning] **FAIL** (12.3704s) 
- `A04` [reasoning] **PASS** (12.0976s) 
- `A05` [reasoning] **FAIL** (14.4699s) 
- `B01` [memory] **PASS** (33.9391s) 
- `B02` [memory] **PASS** (42.5523s) 
- `B03` [memory] **PASS** (44.4439s) 
- `B04` [memory] **PASS** (134.1407s) 
- `B05` [memory] **PASS** (43.5178s) 
- `C01` [tools] **FAIL** (45.5424s) 
- `C02` [tools] **FAIL** (48.568s) 
- `C03` [tools] **PASS** (48.6933s) 
- `C04` [tools] **PASS** (48.6512s) 
- `C05` [tools] **PASS** (42.3497s) 
- `D01` [persistence] **PASS** (46.0154s) restart_after_setup
- `D02` [persistence] **PASS** (44.7157s) restart_after_setup
- `D03` [persistence] **PASS** (47.8979s) restart_after_setup
- `D04` [persistence] **FAIL** (44.3566s) restart_after_setup
- `D05` [persistence] **PASS** (42.2158s) restart_after_setup
- `E01` [long_task] **FAIL** (49.1305s) 
- `E02` [long_task] **FAIL** (45.39s) 
- `E03` [long_task] **FAIL** (86.8809s) 
- `E04` [long_task] **FAIL** (47.8247s) 
- `E05` [long_task] **FAIL** (91.5848s) 
- `F01` [truthfulness] **PASS** (0.0082s) 
- `F02` [truthfulness] **PASS** (0.0064s) 
- `F03` [truthfulness] **PASS** (0.0066s) 
- `F04` [truthfulness] **PASS** (0.006s) 
- `F05` [truthfulness] **PASS** (0.0066s) 
