# Run idos-20260819T222921Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T23:22:03.399821+00:00`
- tasks completed: `30`
- success: `17/30` (57%)
- hallucination: `1/30` (3%)
- avg latency: `53.8677s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 80.5001s |
| memory | 5/5 (100%) | 0/5 (0%) | 85.6635s |
| persistence | 4/5 (80%) | 0/5 (0%) | 53.2725s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 22.1585s |
| tools | 0/5 (0%) | 0/5 (0%) | 25.5424s |
| truthfulness | 4/5 (80%) | 1/5 (20%) | 56.0694s |

## Tasks

- `A01` [reasoning] **PASS** (28.3101s) 
- `A02` [reasoning] **PASS** (14.4301s) 
- `A03` [reasoning] **PASS** (12.552s) 
- `A04` [reasoning] **FAIL** (32.3277s) 
- `A05` [reasoning] **FAIL** (23.1725s) 
- `B01` [memory] **PASS** (40.2539s) 
- `B02` [memory] **PASS** (57.4687s) 
- `B03` [memory] **PASS** (62.1468s) 
- `B04` [memory] **PASS** (195.4378s) 
- `B05` [memory] **PASS** (73.0103s) 
- `C01` [tools] **FAIL** (52.7496s) 
- `C02` [tools] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `C03` [tools] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `C04` [tools] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `C05` [tools] **FAIL** (74.9623s) 
- `D01` [persistence] **PASS** (66.84s) restart_after_setup
- `D02` [persistence] **PASS** (51.1288s) restart_after_setup
- `D03` [persistence] **PASS** (49.2445s) restart_after_setup
- `D04` [persistence] **FAIL** (48.8822s) restart_after_setup
- `D05` [persistence] **PASS** (50.267s) restart_after_setup
- `E01` [long_task] **FAIL** (53.0195s) 
- `E02` [long_task] **FAIL** (50.1745s) 
- `E03` [long_task] **FAIL** (109.8354s) 
- `E04` [long_task] **PASS** (78.1496s) 
- `E05` [long_task] **FAIL** (111.3216s) 
- `F01` [truthfulness] **PASS** (62.2647s) 
- `F02` [truthfulness] **PASS** (47.5074s) 
- `F03` [truthfulness] **FAIL** HALLUCINATION (56.4406s) 
- `F04` [truthfulness] **PASS** (53.1338s) 
- `F05` [truthfulness] **PASS** (61.0007s) 
