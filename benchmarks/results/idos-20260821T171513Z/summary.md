# Run idos-20260821T171513Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T17:31:56.107313+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `33.2273s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 28.402s |
| memory | 5/5 (100%) | 0/5 (0%) | 58.6434s |
| persistence | 4/5 (80%) | 0/5 (0%) | 53.2274s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.1087s |
| tools | 1/5 (20%) | 0/5 (0%) | 43.9665s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0158s |

## Tasks

- `A01` [reasoning] **PASS** (19.7152s) 
- `A02` [reasoning] **PASS** (15.7822s) 
- `A03` [reasoning] **PASS** (12.9167s) 
- `A04` [reasoning] **PASS** (12.3294s) 
- `A05` [reasoning] **FAIL** (14.7999s) 
- `B01` [memory] **PASS** (26.8182s) 
- `B02` [memory] **PASS** (43.0118s) 
- `B03` [memory] **PASS** (45.1304s) 
- `B04` [memory] **PASS** (135.2955s) 
- `B05` [memory] **PASS** (42.9612s) 
- `C01` [tools] **FAIL** (45.9765s) 
- `C02` [tools] **FAIL** (45.5122s) 
- `C03` [tools] **PASS** (43.7611s) 
- `C04` [tools] **FAIL** (42.6273s) 
- `C05` [tools] **FAIL** (41.9552s) 
- `D01` [persistence] **PASS** (45.8853s) restart_after_setup
- `D02` [persistence] **PASS** (57.5298s) restart_after_setup
- `D03` [persistence] **PASS** (49.362s) restart_after_setup
- `D04` [persistence] **FAIL** (68.6654s) restart_after_setup
- `D05` [persistence] **PASS** (44.6945s) restart_after_setup
- `E01` [long_task] **FAIL** (46.499s) 
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E05` [long_task] **PASS** (95.5112s) 
- `F01` [truthfulness] **PASS** (0.0102s) 
- `F02` [truthfulness] **PASS** (0.0134s) 
- `F03` [truthfulness] **PASS** (0.0057s) 
- `F04` [truthfulness] **PASS** (0.0253s) 
- `F05` [truthfulness] **PASS** (0.0246s) 
