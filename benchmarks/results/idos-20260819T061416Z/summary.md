# Run idos-20260819T061416Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T07:11:03.463019+00:00`
- tasks completed: `30`
- success: `9/30` (30%)
- hallucination: `3/30` (10%)
- avg latency: `63.1404s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 68.4251s |
| memory | 2/5 (40%) | 0/5 (0%) | 98.7526s |
| persistence | 0/5 (0%) | 0/5 (0%) | 94.3362s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 18.9873s |
| tools | 1/5 (20%) | 0/5 (0%) | 46.1516s |
| truthfulness | 2/5 (40%) | 3/5 (60%) | 52.1894s |

## Tasks

- `A01` [reasoning] **FAIL** (39.1725s) 
- `A02` [reasoning] **PASS** (13.9204s) 
- `A03` [reasoning] **PASS** (10.9699s) 
- `A04` [reasoning] **PASS** (12.8117s) 
- `A05` [reasoning] **FAIL** (18.0622s) 
- `B01` [memory] **FAIL** (61.256s) 
- `B02` [memory] **FAIL** (87.8331s) 
- `B03` [memory] **PASS** (92.2802s) 
- `B04` [memory] **PASS** (162.9253s) 
- `B05` [memory] **FAIL** (89.4685s) 
- `C01` [tools] **FAIL** (43.4288s) 
- `C02` [tools] **FAIL** (47.1036s) 
- `C03` [tools] **PASS** (45.5616s) 
- `C04` [tools] **FAIL** (47.7792s) 
- `C05` [tools] **FAIL** (46.8846s) 
- `D01` [persistence] **FAIL** (101.7448s) restart_after_setup
- `D02` [persistence] **FAIL** (97.14s) restart_after_setup
- `D03` [persistence] **FAIL** (87.9887s) restart_after_setup
- `D04` [persistence] **FAIL** (86.3093s) restart_after_setup
- `D05` [persistence] **FAIL** (98.4981s) restart_after_setup
- `E01` [long_task] **FAIL** (56.5597s) 
- `E02` [long_task] **FAIL** (45.1099s) 
- `E03` [long_task] **FAIL** (88.0703s) 
- `E04` [long_task] **PASS** (57.5741s) 
- `E05` [long_task] **FAIL** (94.8113s) 
- `F01` [truthfulness] **FAIL** HALLUCINATION (43.829s) 
- `F02` [truthfulness] **FAIL** HALLUCINATION (42.0434s) 
- `F03` [truthfulness] **PASS** (52.8012s) 
- `F04` [truthfulness] **PASS** (44.9876s) 
- `F05` [truthfulness] **FAIL** HALLUCINATION (77.2858s) 
