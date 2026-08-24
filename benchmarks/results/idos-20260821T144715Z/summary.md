# Run idos-20260821T144715Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T14:59:12.895103+00:00`
- tasks completed: `17`
- success: `10/17` (59%)
- hallucination: `0/17` (0%)
- avg latency: `42.1841s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 5/5 (100%) | 0/5 (0%) | 65.3027s |
| persistence | 2/2 (100%) | 0/2 (0%) | 45.2381s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 12.6417s |
| tools | 1/5 (20%) | 0/5 (0%) | 47.3862s |

## Tasks

- `A01` [reasoning] **FAIL** (13.1752s) 
- `A02` [reasoning] **PASS** (12.0957s) 
- `A03` [reasoning] **FAIL** (11.9669s) 
- `A04` [reasoning] **PASS** (11.8999s) 
- `A05` [reasoning] **FAIL** (14.0707s) 
- `B01` [memory] **PASS** (49.5438s) 
- `B02` [memory] **PASS** (41.0309s) 
- `B03` [memory] **PASS** (45.1297s) 
- `B04` [memory] **PASS** (144.8817s) 
- `B05` [memory] **PASS** (45.9274s) 
- `C01` [tools] **FAIL** (42.0879s) 
- `C02` [tools] **FAIL** (52.0502s) 
- `C03` [tools] **PASS** (42.5421s) 
- `C04` [tools] **FAIL** (40.8879s) 
- `C05` [tools] **FAIL** (59.363s) 
- `D01` [persistence] **PASS** (44.73s) restart_after_setup
- `D02` [persistence] **PASS** (45.7463s) restart_after_setup
