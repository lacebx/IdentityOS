# Run bare-20260825T053858Z

- mode: `bare`
- model: `phi4-mini`
- benchmark: `v0.1.0`
- updated_at: `2026-08-25T05:46:36.262167+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `15.2668s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 5/5 (100%) | 0/5 (0%) | 19.1137s |
| memory | 5/5 (100%) | 0/5 (0%) | 22.9003s |
| persistence | 0/5 (0%) | 0/5 (0%) | 19.7598s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 2.7261s |
| tools | 2/5 (40%) | 0/5 (0%) | 10.3461s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 16.7545s |

## Tasks

- `A01` [reasoning] **PASS** (2.4737s) 
- `A02` [reasoning] **PASS** (4.8605s) 
- `A03` [reasoning] **PASS** (1.5647s) 
- `A04` [reasoning] **PASS** (2.5373s) 
- `A05` [reasoning] **FAIL** (2.1945s) 
- `B01` [memory] **PASS** (24.1082s) 
- `B02` [memory] **PASS** (4.4986s) 
- `B03` [memory] **PASS** (23.5472s) 
- `B04` [memory] **PASS** (54.6983s) 
- `B05` [memory] **PASS** (7.6493s) 
- `C01` [tools] **FAIL** (3.9542s) 
- `C02` [tools] **FAIL** (25.4787s) 
- `C03` [tools] **FAIL** (17.195s) 
- `C04` [tools] **PASS** (2.3029s) 
- `C05` [tools] **PASS** (2.7999s) 
- `D01` [persistence] **FAIL** (33.193s) restart_after_setup
- `D02` [persistence] **FAIL** (13.553s) restart_after_setup
- `D03` [persistence] **FAIL** (11.0248s) restart_after_setup
- `D04` [persistence] **FAIL** (18.6524s) restart_after_setup
- `D05` [persistence] **FAIL** (22.3759s) restart_after_setup
- `E01` [long_task] **PASS** (13.7404s) 
- `E02` [long_task] **PASS** (14.4174s) 
- `E03` [long_task] **PASS** (10.6611s) 
- `E04` [long_task] **PASS** (33.3336s) 
- `E05` [long_task] **PASS** (23.4158s) 
- `F01` [truthfulness] **PASS** (14.8665s) 
- `F02` [truthfulness] **PASS** (15.5368s) 
- `F03` [truthfulness] **PASS** (15.3753s) 
- `F04` [truthfulness] **PASS** (12.32s) 
- `F05` [truthfulness] **PASS** (25.674s) 
