# Run idos-20260819T215953Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T22:28:26.885719+00:00`
- tasks completed: `30`
- success: `22/30` (73%)
- hallucination: `1/30` (3%)
- avg latency: `57.1056s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 3/5 (60%) | 0/5 (0%) | 67.5833s |
| memory | 5/5 (100%) | 0/5 (0%) | 80.3074s |
| persistence | 4/5 (80%) | 0/5 (0%) | 48.8389s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.3897s |
| tools | 2/5 (40%) | 0/5 (0%) | 44.4106s |
| truthfulness | 4/5 (80%) | 1/5 (20%) | 86.1039s |

## Tasks

- `A01` [reasoning] **PASS** (16.1204s) 
- `A02` [reasoning] **PASS** (16.1407s) 
- `A03` [reasoning] **PASS** (14.3759s) 
- `A04` [reasoning] **PASS** (15.2952s) 
- `A05` [reasoning] **FAIL** (15.0165s) 
- `B01` [memory] **PASS** (56.813s) 
- `B02` [memory] **PASS** (47.93s) 
- `B03` [memory] **PASS** (44.2987s) 
- `B04` [memory] **PASS** (203.9172s) 
- `B05` [memory] **PASS** (48.5779s) 
- `C01` [tools] **FAIL** (43.7322s) 
- `C02` [tools] **FAIL** (45.9818s) 
- `C03` [tools] **PASS** (44.3955s) 
- `C04` [tools] **PASS** (42.4665s) 
- `C05` [tools] **FAIL** (45.4769s) 
- `D01` [persistence] **PASS** (45.6468s) restart_after_setup
- `D02` [persistence] **PASS** (54.2243s) restart_after_setup
- `D03` [persistence] **PASS** (45.8062s) restart_after_setup
- `D04` [persistence] **FAIL** (42.2263s) restart_after_setup
- `D05` [persistence] **PASS** (56.291s) restart_after_setup
- `E01` [long_task] **PASS** (51.732s) 
- `E02` [long_task] **FAIL** (47.991s) 
- `E03` [long_task] **FAIL** (94.1842s) 
- `E04` [long_task] **PASS** (51.3792s) 
- `E05` [long_task] **PASS** (92.63s) 
- `F01` [truthfulness] **PASS** (125.529s) 
- `F02` [truthfulness] **PASS** (73.5479s) 
- `F03` [truthfulness] **FAIL** HALLUCINATION (96.6735s) 
- `F04` [truthfulness] **PASS** (60.9044s) 
- `F05` [truthfulness] **PASS** (73.8645s) 
