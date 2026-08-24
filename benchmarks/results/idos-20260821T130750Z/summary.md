# Run idos-20260821T130750Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T13:29:44.043343+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `43.7777s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 63.0721s |
| memory | 4/5 (80%) | 0/5 (0%) | 64.5236s |
| persistence | 4/5 (80%) | 0/5 (0%) | 57.5287s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 34.238s |
| tools | 1/5 (20%) | 0/5 (0%) | 43.2969s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0067s |

## Tasks

- `A01` [reasoning] **PASS** (28.0019s) 
- `A02` [reasoning] **PASS** (11.8779s) 
- `A03` [reasoning] **PASS** (10.8748s) 
- `A04` [reasoning] **PASS** (80.957s) 
- `A05` [reasoning] **FAIL** (39.4784s) 
- `B01` [memory] **PASS** (59.6506s) 
- `B02` [memory] **PASS** (40.0308s) 
- `B03` [memory] **PASS** (41.4513s) 
- `B04` [memory] **FAIL** (136.2291s) 
- `B05` [memory] **PASS** (45.256s) 
- `C01` [tools] **FAIL** (43.0733s) 
- `C02` [tools] **FAIL** (43.3389s) 
- `C03` [tools] **PASS** (44.3071s) 
- `C04` [tools] **FAIL** (40.4378s) 
- `C05` [tools] **FAIL** (45.3273s) 
- `D01` [persistence] **PASS** (46.2269s) restart_after_setup
- `D02` [persistence] **PASS** (107.0627s) restart_after_setup
- `D03` [persistence] **PASS** (45.6546s) restart_after_setup
- `D04` [persistence] **FAIL** (46.2092s) restart_after_setup
- `D05` [persistence] **PASS** (42.4901s) restart_after_setup
- `E01` [long_task] **FAIL** (43.2058s) 
- `E02` [long_task] **FAIL** (44.022s) 
- `E03` [long_task] **FAIL** (86.8356s) 
- `E04` [long_task] **PASS** (47.4104s) 
- `E05` [long_task] **FAIL** (93.8868s) 
- `F01` [truthfulness] **PASS** (0.0079s) 
- `F02` [truthfulness] **PASS** (0.0061s) 
- `F03` [truthfulness] **PASS** (0.0071s) 
- `F04` [truthfulness] **PASS** (0.006s) 
- `F05` [truthfulness] **PASS** (0.0064s) 
