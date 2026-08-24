# Run idos-20260821T113736Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T11:53:27.864850+00:00`
- tasks completed: `24`
- success: `14/24` (58%)
- hallucination: `0/24` (0%)
- avg latency: `39.4066s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/4 (0%) | 0/4 (0%) | 24.6618s |
| memory | 5/5 (100%) | 0/5 (0%) | 61.2638s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.1957s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 16.1629s |
| tools | 2/5 (40%) | 0/5 (0%) | 44.7998s |

## Tasks

- `A01` [reasoning] **FAIL** (28.279s) 
- `A02` [reasoning] **PASS** (11.2558s) 
- `A03` [reasoning] **PASS** (12.8082s) 
- `A04` [reasoning] **PASS** (13.335s) 
- `A05` [reasoning] **FAIL** (15.1363s) 
- `B01` [memory] **PASS** (24.7484s) 
- `B02` [memory] **PASS** (47.9406s) 
- `B03` [memory] **PASS** (44.9767s) 
- `B04` [memory] **PASS** (142.7387s) 
- `B05` [memory] **PASS** (45.9148s) 
- `C01` [tools] **FAIL** (44.0276s) 
- `C02` [tools] **FAIL** (48.1144s) 
- `C03` [tools] **PASS** (43.9759s) 
- `C04` [tools] **FAIL** (43.5094s) 
- `C05` [tools] **PASS** (44.3718s) 
- `D01` [persistence] **PASS** (49.1174s) restart_after_setup
- `D02` [persistence] **PASS** (50.6143s) restart_after_setup
- `D03` [persistence] **PASS** (44.5237s) restart_after_setup
- `D04` [persistence] **FAIL** (41.5855s) restart_after_setup
- `D05` [persistence] **PASS** (50.1378s) restart_after_setup
- `E01` [long_task] **FAIL** (42.6446s) 
- `E02` [long_task] **FAIL** (56.0025s) 
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
