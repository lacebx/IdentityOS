# Run idos-20260821T160009Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T16:20:29.760789+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `39.5621s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 59.1734s |
| memory | 5/5 (100%) | 0/5 (0%) | 66.1167s |
| persistence | 4/5 (80%) | 0/5 (0%) | 48.4889s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 12.9683s |
| tools | 2/5 (40%) | 0/5 (0%) | 50.6148s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0104s |

## Tasks

- `A01` [reasoning] **PASS** (11.1829s) 
- `A02` [reasoning] **PASS** (11.557s) 
- `A03` [reasoning] **FAIL** (10.3723s) 
- `A04` [reasoning] **PASS** (15.8095s) 
- `A05` [reasoning] **FAIL** (15.9198s) 
- `B01` [memory] **PASS** (55.789s) 
- `B02` [memory] **PASS** (46.0007s) 
- `B03` [memory] **PASS** (42.2231s) 
- `B04` [memory] **PASS** (139.3742s) 
- `B05` [memory] **PASS** (47.1963s) 
- `C01` [tools] **FAIL** (41.6528s) 
- `C02` [tools] **FAIL** (62.2005s) 
- `C03` [tools] **FAIL** (54.1492s) 
- `C04` [tools] **PASS** (47.3672s) 
- `C05` [tools] **PASS** (47.7045s) 
- `D01` [persistence] **PASS** (45.4157s) restart_after_setup
- `D02` [persistence] **PASS** (41.7289s) restart_after_setup
- `D03` [persistence] **PASS** (45.0478s) restart_after_setup
- `D04` [persistence] **FAIL** (44.6618s) restart_after_setup
- `D05` [persistence] **PASS** (65.5904s) restart_after_setup
- `E01` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (100.1466s) 
- `E04` [long_task] **PASS** (93.056s) 
- `E05` [long_task] **FAIL** (102.6645s) 
- `F01` [truthfulness] **PASS** (0.0083s) 
- `F02` [truthfulness] **PASS** (0.013s) 
- `F03` [truthfulness] **PASS** (0.0099s) 
- `F04` [truthfulness] **PASS** (0.0101s) 
- `F05` [truthfulness] **PASS** (0.0108s) 
