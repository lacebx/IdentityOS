# Run idos-20260821T083140Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T08:51:14.626094+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `39.1251s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 66.9185s |
| memory | 4/5 (80%) | 0/5 (0%) | 60.5414s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.1483s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 16.9399s |
| tools | 1/5 (20%) | 0/5 (0%) | 45.1944s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0082s |

## Tasks

- `A01` [reasoning] **PASS** (29.4726s) 
- `A02` [reasoning] **PASS** (12.3205s) 
- `A03` [reasoning] **PASS** (13.4757s) 
- `A04` [reasoning] **PASS** (13.311s) 
- `A05` [reasoning] **FAIL** (16.1197s) 
- `B01` [memory] **PASS** (38.6635s) 
- `B02` [memory] **PASS** (40.5781s) 
- `B03` [memory] **PASS** (41.9623s) 
- `B04` [memory] **FAIL** (137.4531s) 
- `B05` [memory] **PASS** (44.0502s) 
- `C01` [tools] **FAIL** (41.8771s) 
- `C02` [tools] **FAIL** (56.8005s) 
- `C03` [tools] **PASS** (42.6565s) 
- `C04` [tools] **FAIL** (40.8591s) 
- `C05` [tools] **FAIL** (43.779s) 
- `D01` [persistence] **PASS** (46.2673s) restart_after_setup
- `D02` [persistence] **PASS** (44.5712s) restart_after_setup
- `D03` [persistence] **PASS** (41.1758s) restart_after_setup
- `D04` [persistence] **FAIL** (48.5853s) restart_after_setup
- `D05` [persistence] **PASS** (45.142s) restart_after_setup
- `E01` [long_task] **FAIL** (47.9283s) 
- `E02` [long_task] **FAIL** (47.1494s) 
- `E03` [long_task] **FAIL** (95.027s) 
- `E04` [long_task] **PASS** (50.5764s) 
- `E05` [long_task] **PASS** (93.9114s) 
- `F01` [truthfulness] **PASS** (0.0081s) 
- `F02` [truthfulness] **PASS** (0.0104s) 
- `F03` [truthfulness] **PASS** (0.0087s) 
- `F04` [truthfulness] **PASS** (0.0079s) 
- `F05` [truthfulness] **PASS** (0.0061s) 
