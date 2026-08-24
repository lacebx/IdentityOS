# Run idos-20260819T211800Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T21:49:08.559463+00:00`
- tasks completed: `30`
- success: `12/30` (40%)
- hallucination: `0/30` (0%)
- avg latency: `62.252s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 66.1625s |
| memory | 2/5 (40%) | 0/5 (0%) | 108.7131s |
| persistence | 0/5 (0%) | 0/5 (0%) | 91.2328s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 19.3475s |
| tools | 2/5 (40%) | 0/5 (0%) | 41.8134s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 46.2429s |

## Tasks

- `A01` [reasoning] **PASS** (38.3256s) 
- `A02` [reasoning] **PASS** (13.4431s) 
- `A03` [reasoning] **FAIL** (13.189s) 
- `A04` [reasoning] **FAIL** (14.261s) 
- `A05` [reasoning] **FAIL** (17.519s) 
- `B01` [memory] **PASS** (85.1367s) 
- `B02` [memory] **PASS** (114.0768s) 
- `B03` [memory] **FAIL** (100.7546s) 
- `B04` [memory] **FAIL** (155.4604s) 
- `B05` [memory] **FAIL** (88.1371s) 
- `C01` [tools] **FAIL** (40.4754s) 
- `C02` [tools] **FAIL** (44.2861s) 
- `C03` [tools] **PASS** (42.9339s) 
- `C04` [tools] **FAIL** (40.7993s) 
- `C05` [tools] **PASS** (40.5722s) 
- `D01` [persistence] **FAIL** (93.9831s) restart_after_setup
- `D02` [persistence] **FAIL** (89.1385s) restart_after_setup
- `D03` [persistence] **FAIL** (92.8556s) restart_after_setup
- `D04` [persistence] **FAIL** (88.9095s) restart_after_setup
- `D05` [persistence] **FAIL** (91.2775s) restart_after_setup
- `E01` [long_task] **FAIL** (43.394s) 
- `E02` [long_task] **FAIL** (48.7106s) 
- `E03` [long_task] **FAIL** (101.6939s) 
- `E04` [long_task] **PASS** (45.2484s) 
- `E05` [long_task] **FAIL** (91.7658s) 
- `F01` [truthfulness] **PASS** (47.2994s) 
- `F02` [truthfulness] **PASS** (43.1271s) 
- `F03` [truthfulness] **PASS** (46.5604s) 
- `F04` [truthfulness] **PASS** (46.7899s) 
- `F05` [truthfulness] **PASS** (47.4375s) 
