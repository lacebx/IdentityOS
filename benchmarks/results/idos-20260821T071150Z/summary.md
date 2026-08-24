# Run idos-20260821T071150Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T07:39:36.235067+00:00`
- tasks completed: `24`
- success: `16/24` (67%)
- hallucination: `0/24` (0%)
- avg latency: `59.9501s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/4 (0%) | 0/4 (0%) | 124.7525s |
| memory | 5/5 (100%) | 0/5 (0%) | 68.664s |
| persistence | 4/5 (80%) | 0/5 (0%) | 52.4481s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 16.1743s |
| tools | 3/5 (60%) | 0/5 (0%) | 50.6722s |

## Tasks

- `A01` [reasoning] **PASS** (25.4609s) 
- `A02` [reasoning] **PASS** (13.7465s) 
- `A03` [reasoning] **PASS** (12.3185s) 
- `A04` [reasoning] **PASS** (13.3127s) 
- `A05` [reasoning] **FAIL** (16.0327s) 
- `B01` [memory] **PASS** (31.8026s) 
- `B02` [memory] **PASS** (51.3799s) 
- `B03` [memory] **PASS** (51.8047s) 
- `B04` [memory] **PASS** (162.3397s) 
- `B05` [memory] **PASS** (45.9931s) 
- `C01` [tools] **FAIL** (50.0616s) 
- `C02` [tools] **FAIL** (54.5869s) 
- `C03` [tools] **PASS** (47.0262s) 
- `C04` [tools] **PASS** (55.4108s) 
- `C05` [tools] **PASS** (46.2756s) 
- `D01` [persistence] **PASS** (53.175s) restart_after_setup
- `D02` [persistence] **PASS** (49.193s) restart_after_setup
- `D03` [persistence] **PASS** (45.7255s) restart_after_setup
- `D04` [persistence] **FAIL** (48.8151s) restart_after_setup
- `D05` [persistence] **PASS** (65.3317s) restart_after_setup
- `E01` [long_task] **FAIL** (499.0099s) 
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
