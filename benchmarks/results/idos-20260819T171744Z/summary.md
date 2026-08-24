# Run idos-20260819T171744Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T17:42:55.228957+00:00`
- tasks completed: `17`
- success: `7/17` (41%)
- hallucination: `0/17` (0%)
- avg latency: `88.446s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 2/5 (40%) | 0/5 (0%) | 108.9556s |
| persistence | 0/2 (0%) | 0/2 (0%) | 344.3331s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 11.847s |
| tools | 2/5 (40%) | 0/5 (0%) | 42.1806s |

## Tasks

- `A01` [reasoning] **FAIL** (13.0382s) 
- `A02` [reasoning] **PASS** (9.862s) 
- `A03` [reasoning] **PASS** (10.1821s) 
- `A04` [reasoning] **PASS** (11.6331s) 
- `A05` [reasoning] **FAIL** (14.5197s) 
- `B01` [memory] **FAIL** (70.5838s) 
- `B02` [memory] **FAIL** (99.7252s) 
- `B03` [memory] **PASS** (86.1304s) 
- `B04` [memory] **PASS** (195.9033s) 
- `B05` [memory] **FAIL** (92.4352s) 
- `C01` [tools] **FAIL** (42.2479s) 
- `C02` [tools] **FAIL** (44.0036s) 
- `C03` [tools] **PASS** (41.7655s) 
- `C04` [tools] **FAIL** (40.8132s) 
- `C05` [tools] **PASS** (42.0726s) 
- `D01` [persistence] **FAIL** (97.6231s) restart_after_setup
- `D02` [persistence] **FAIL** (591.043s) restart_after_setup; error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
