# Run idos-20260821T101857Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T10:40:19.814533+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `42.5565s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 78.0635s |
| memory | 5/5 (100%) | 0/5 (0%) | 70.0598s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.4318s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 18.9197s |
| tools | 1/5 (20%) | 0/5 (0%) | 40.8547s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0095s |

## Tasks

- `A01` [reasoning] **PASS** (37.4241s) 
- `A02` [reasoning] **PASS** (12.4557s) 
- `A03` [reasoning] **PASS** (10.6072s) 
- `A04` [reasoning] **PASS** (16.8444s) 
- `A05` [reasoning] **FAIL** (17.2669s) 
- `B01` [memory] **PASS** (25.5903s) 
- `B02` [memory] **PASS** (56.3366s) 
- `B03` [memory] **PASS** (55.4451s) 
- `B04` [memory] **PASS** (169.803s) 
- `B05` [memory] **PASS** (43.124s) 
- `C01` [tools] **FAIL** (42.2201s) 
- `C02` [tools] **FAIL** (75.6605s) 
- `C03` [tools] **PASS** (43.7447s) 
- `C04` [tools] **FAIL** (42.6481s) 
- `C05` [tools] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `D01` [persistence] **PASS** (59.4018s) restart_after_setup
- `D02` [persistence] **PASS** (43.2896s) restart_after_setup
- `D03` [persistence] **PASS** (44.1618s) restart_after_setup
- `D04` [persistence] **FAIL** (45.6954s) restart_after_setup
- `D05` [persistence] **PASS** (44.6104s) restart_after_setup
- `E01` [long_task] **FAIL** (44.1226s) 
- `E02` [long_task] **FAIL** (46.2726s) 
- `E03` [long_task] **PASS** (110.0523s) 
- `E04` [long_task] **PASS** (102.1167s) 
- `E05` [long_task] **FAIL** (87.7534s) 
- `F01` [truthfulness] **PASS** (0.0082s) 
- `F02` [truthfulness] **PASS** (0.0095s) 
- `F03` [truthfulness] **PASS** (0.0083s) 
- `F04` [truthfulness] **PASS** (0.0086s) 
- `F05` [truthfulness] **PASS** (0.013s) 
