# Run idos-20260821T122109Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T12:38:35.005209+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `34.696s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 39.1522s |
| memory | 4/5 (80%) | 0/5 (0%) | 59.4382s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.2924s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 13.4039s |
| tools | 2/5 (40%) | 0/5 (0%) | 48.8833s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0061s |

## Tasks

- `A01` [reasoning] **PASS** (15.6523s) 
- `A02` [reasoning] **PASS** (13.1934s) 
- `A03` [reasoning] **PASS** (11.0443s) 
- `A04` [reasoning] **PASS** (11.9538s) 
- `A05` [reasoning] **FAIL** (15.1757s) 
- `B01` [memory] **PASS** (29.5914s) 
- `B02` [memory] **PASS** (44.359s) 
- `B03` [memory] **PASS** (44.24s) 
- `B04` [memory] **FAIL** (137.5532s) 
- `B05` [memory] **PASS** (41.4475s) 
- `C01` [tools] **FAIL** (42.4452s) 
- `C02` [tools] **FAIL** (45.0872s) 
- `C03` [tools] **PASS** (45.8969s) 
- `C04` [tools] **FAIL** (68.2606s) 
- `C05` [tools] **PASS** (42.7265s) 
- `D01` [persistence] **PASS** (45.5022s) restart_after_setup
- `D02` [persistence] **PASS** (47.0222s) restart_after_setup
- `D03` [persistence] **PASS** (43.8023s) restart_after_setup
- `D04` [persistence] **FAIL** (44.6204s) restart_after_setup
- `D05` [persistence] **PASS** (55.5151s) restart_after_setup
- `E01` [long_task] **FAIL** (45.6564s) 
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (59.7002s) 
- `E05` [long_task] **FAIL** (90.4044s) 
- `F01` [truthfulness] **PASS** (0.0062s) 
- `F02` [truthfulness] **PASS** (0.006s) 
- `F03` [truthfulness] **PASS** (0.0057s) 
- `F04` [truthfulness] **PASS** (0.0056s) 
- `F05` [truthfulness] **PASS** (0.007s) 
