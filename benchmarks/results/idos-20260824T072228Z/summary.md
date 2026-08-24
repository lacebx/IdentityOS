# Run idos-20260824T072228Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T07:35:29.487517+00:00`
- tasks completed: `18`
- success: `9/18` (50%)
- hallucination: `0/18` (0%)
- avg latency: `43.3657s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 4/5 (80%) | 0/5 (0%) | 58.6061s |
| persistence | 3/3 (100%) | 0/3 (0%) | 50.8228s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 16.5674s |
| tools | 0/5 (0%) | 0/5 (0%) | 50.4493s |

## Tasks

- `A01` [reasoning] **FAIL** (29.8403s) 
- `A02` [reasoning] **PASS** (15.3883s) 
- `A03` [reasoning] **FAIL** (10.5068s) 
- `A04` [reasoning] **PASS** (11.8206s) 
- `A05` [reasoning] **FAIL** (15.281s) 
- `B01` [memory] **PASS** (24.0877s) 
- `B02` [memory] **PASS** (31.125s) 
- `B03` [memory] **PASS** (48.317s) 
- `B04` [memory] **FAIL** (147.4265s) 
- `B05` [memory] **PASS** (42.0742s) 
- `C01` [tools] **FAIL** (46.8558s) 
- `C02` [tools] **FAIL** (68.3649s) 
- `C03` [tools] **FAIL** (45.7774s) 
- `C04` [tools] **FAIL** (47.3735s) 
- `C05` [tools] **FAIL** (43.8747s) 
- `D01` [persistence] **PASS** (49.135s) restart_after_setup
- `D02` [persistence] **PASS** (52.8881s) restart_after_setup
- `D03` [persistence] **PASS** (50.4453s) restart_after_setup
