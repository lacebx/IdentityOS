# Run idos-20260820T000406Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-20T00:31:42.236415+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `2/30` (7%)
- avg latency: `55.1094s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 71.1368s |
| memory | 5/5 (100%) | 0/5 (0%) | 107.8679s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.9277s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 24.0835s |
| tools | 3/5 (60%) | 0/5 (0%) | 44.0058s |
| truthfulness | 3/5 (60%) | 2/5 (40%) | 37.6347s |

## Tasks

- `A01` [reasoning] **PASS** (45.0578s) 
- `A02` [reasoning] **PASS** (17.7556s) 
- `A03` [reasoning] **PASS** (19.7291s) 
- `A04` [reasoning] **PASS** (18.2642s) 
- `A05` [reasoning] **FAIL** (19.6106s) 
- `B01` [memory] **PASS** (33.2834s) 
- `B02` [memory] **PASS** (53.1376s) 
- `B03` [memory] **PASS** (54.5025s) 
- `B04` [memory] **PASS** (344.0044s) 
- `B05` [memory] **PASS** (54.4118s) 
- `C01` [tools] **FAIL** (40.5231s) 
- `C02` [tools] **FAIL** (48.1484s) 
- `C03` [tools] **PASS** (43.3961s) 
- `C04` [tools] **PASS** (40.8243s) 
- `C05` [tools] **PASS** (47.137s) 
- `D01` [persistence] **PASS** (54.3483s) restart_after_setup
- `D02` [persistence] **PASS** (41.2021s) restart_after_setup
- `D03` [persistence] **PASS** (43.5225s) restart_after_setup
- `D04` [persistence] **FAIL** (43.3455s) restart_after_setup
- `D05` [persistence] **PASS** (47.2199s) restart_after_setup
- `E01` [long_task] **FAIL** (45.5531s) 
- `E02` [long_task] **FAIL** (45.4187s) 
- `E03` [long_task] **FAIL** (93.9547s) 
- `E04` [long_task] **PASS** (71.5079s) 
- `E05` [long_task] **FAIL** (99.2497s) 
- `F01` [truthfulness] **FAIL** HALLUCINATION (47.1771s) 
- `F02` [truthfulness] **FAIL** HALLUCINATION (48.4056s) 
- `F03` [truthfulness] **PASS** (0.0067s) 
- `F04` [truthfulness] **PASS** (42.1999s) 
- `F05` [truthfulness] **PASS** (50.3844s) 
