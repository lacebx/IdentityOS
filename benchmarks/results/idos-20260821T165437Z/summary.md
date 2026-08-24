# Run idos-20260821T165437Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T17:13:58.871824+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `38.7065s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 64.7684s |
| memory | 4/5 (80%) | 0/5 (0%) | 60.7172s |
| persistence | 4/5 (80%) | 0/5 (0%) | 43.0346s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 17.1256s |
| tools | 2/5 (40%) | 0/5 (0%) | 46.5844s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.009s |

## Tasks

- `A01` [reasoning] **PASS** (36.2888s) 
- `A02` [reasoning] **PASS** (12.5157s) 
- `A03` [reasoning] **PASS** (10.9201s) 
- `A04` [reasoning] **PASS** (11.8912s) 
- `A05` [reasoning] **FAIL** (14.012s) 
- `B01` [memory] **PASS** (23.6902s) 
- `B02` [memory] **PASS** (47.3176s) 
- `B03` [memory] **PASS** (44.0142s) 
- `B04` [memory] **FAIL** (144.1032s) 
- `B05` [memory] **PASS** (44.4607s) 
- `C01` [tools] **FAIL** (40.0953s) 
- `C02` [tools] **FAIL** (56.3169s) 
- `C03` [tools] **PASS** (43.1857s) 
- `C04` [tools] **FAIL** (52.3995s) 
- `C05` [tools] **PASS** (40.9244s) 
- `D01` [persistence] **PASS** (42.3317s) restart_after_setup
- `D02` [persistence] **PASS** (40.8856s) restart_after_setup
- `D03` [persistence] **PASS** (43.3147s) restart_after_setup
- `D04` [persistence] **FAIL** (42.6646s) restart_after_setup
- `D05` [persistence] **PASS** (45.9764s) restart_after_setup
- `E01` [long_task] **FAIL** (43.0784s) 
- `E02` [long_task] **FAIL** (45.9773s) 
- `E03` [long_task] **FAIL** (84.6s) 
- `E04` [long_task] **PASS** (54.2523s) 
- `E05` [long_task] **FAIL** (95.9341s) 
- `F01` [truthfulness] **PASS** (0.0104s) 
- `F02` [truthfulness] **PASS** (0.0109s) 
- `F03` [truthfulness] **PASS** (0.0072s) 
- `F04` [truthfulness] **PASS** (0.0084s) 
- `F05` [truthfulness] **PASS** (0.0079s) 
