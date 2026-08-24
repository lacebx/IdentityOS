# Run idos-20260821T140623Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T14:25:54.595588+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `38.897s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 52.8287s |
| memory | 5/5 (100%) | 0/5 (0%) | 73.7897s |
| persistence | 4/5 (80%) | 0/5 (0%) | 43.6699s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 15.2901s |
| tools | 1/5 (20%) | 0/5 (0%) | 47.7976s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0057s |

## Tasks

- `A01` [reasoning] **FAIL** (21.7968s) 
- `A02` [reasoning] **PASS** (16.0186s) 
- `A03` [reasoning] **PASS** (11.3057s) 
- `A04` [reasoning] **FAIL** (12.1783s) 
- `A05` [reasoning] **FAIL** (15.1509s) 
- `B01` [memory] **PASS** (27.5362s) 
- `B02` [memory] **PASS** (108.7318s) 
- `B03` [memory] **PASS** (43.7324s) 
- `B04` [memory] **PASS** (141.9951s) 
- `B05` [memory] **PASS** (46.9532s) 
- `C01` [tools] **FAIL** (41.9658s) 
- `C02` [tools] **FAIL** (44.5627s) 
- `C03` [tools] **PASS** (49.4594s) 
- `C04` [tools] **FAIL** (55.1399s) 
- `C05` [tools] **FAIL** (47.8604s) 
- `D01` [persistence] **PASS** (43.1841s) restart_after_setup
- `D02` [persistence] **PASS** (44.4947s) restart_after_setup
- `D03` [persistence] **PASS** (45.6509s) restart_after_setup
- `D04` [persistence] **FAIL** (42.1877s) restart_after_setup
- `D05` [persistence] **PASS** (42.8319s) restart_after_setup
- `E01` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **PASS** (62.5521s) 
- `E04` [long_task] **PASS** (105.5655s) 
- `E05` [long_task] **FAIL** (96.0261s) 
- `F01` [truthfulness] **PASS** (0.0056s) 
- `F02` [truthfulness] **PASS** (0.0056s) 
- `F03` [truthfulness] **PASS** (0.0058s) 
- `F04` [truthfulness] **PASS** (0.0056s) 
- `F05` [truthfulness] **PASS** (0.0058s) 
