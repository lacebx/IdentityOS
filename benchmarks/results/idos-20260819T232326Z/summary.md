# Run idos-20260819T232326Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-20T00:03:23.143613+00:00`
- tasks completed: `30`
- success: `15/30` (50%)
- hallucination: `1/30` (3%)
- avg latency: `49.911s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 45.0552s |
| memory | 5/5 (100%) | 0/5 (0%) | 68.9352s |
| persistence | 4/5 (80%) | 0/5 (0%) | 56.7709s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 17.5193s |
| tools | 0/5 (0%) | 0/5 (0%) | 70.4995s |
| truthfulness | 4/5 (80%) | 1/5 (20%) | 40.6861s |

## Tasks

- `A01` [reasoning] **PASS** (28.5171s) 
- `A02` [reasoning] **PASS** (14.5583s) 
- `A03` [reasoning] **FAIL** (12.4307s) 
- `A04` [reasoning] **FAIL** (14.307s) 
- `A05` [reasoning] **FAIL** (17.7834s) 
- `B01` [memory] **PASS** (30.3685s) 
- `B02` [memory] **PASS** (47.8934s) 
- `B03` [memory] **PASS** (48.8307s) 
- `B04` [memory] **PASS** (154.8397s) 
- `B05` [memory] **PASS** (62.7439s) 
- `C01` [tools] **FAIL** (48.5513s) 
- `C02` [tools] **FAIL** (90.0409s) 
- `C03` [tools] **FAIL** (56.0445s) 
- `C04` [tools] **FAIL** (51.3504s) 
- `C05` [tools] **FAIL** (106.5102s) 
- `D01` [persistence] **PASS** (55.3311s) restart_after_setup
- `D02` [persistence] **PASS** (61.0042s) restart_after_setup
- `D03` [persistence] **PASS** (54.9913s) restart_after_setup
- `D04` [persistence] **FAIL** (52.7387s) restart_after_setup
- `D05` [persistence] **PASS** (59.7894s) restart_after_setup
- `E01` [long_task] **FAIL** (51.0942s) 
- `E02` [long_task] **FAIL** (57.5665s) 
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E05` [long_task] **FAIL** (116.6155s) 
- `F01` [truthfulness] **FAIL** HALLUCINATION (51.553s) 
- `F02` [truthfulness] **PASS** (51.1249s) 
- `F03` [truthfulness] **PASS** (0.0065s) 
- `F04` [truthfulness] **PASS** (49.1922s) 
- `F05` [truthfulness] **PASS** (51.5537s) 
