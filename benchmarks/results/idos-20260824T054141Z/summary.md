# Run idos-20260824T054141Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T06:18:56.581208+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `74.3258s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 117.0122s |
| memory | 5/5 (100%) | 0/5 (0%) | 60.2466s |
| persistence | 4/5 (80%) | 0/5 (0%) | 71.1899s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 38.0497s |
| tools | 2/5 (40%) | 0/5 (0%) | 159.4451s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0112s |

## Tasks

- `A01` [reasoning] **PASS** (134.3259s) 
- `A02` [reasoning] **PASS** (15.2676s) 
- `A03` [reasoning] **FAIL** (10.7334s) 
- `A04` [reasoning] **PASS** (14.9684s) 
- `A05` [reasoning] **FAIL** (14.9533s) 
- `B01` [memory] **PASS** (47.235s) 
- `B02` [memory] **PASS** (41.3341s) 
- `B03` [memory] **PASS** (40.8821s) 
- `B04` [memory] **PASS** (131.1931s) 
- `B05` [memory] **PASS** (40.5886s) 
- `C01` [tools] **FAIL** (41.2487s) 
- `C02` [tools] **FAIL** (44.271s) 
- `C03` [tools] **PASS** (40.8506s) 
- `C04` [tools] **FAIL** (41.3317s) 
- `C05` [tools] **PASS** (629.5235s) 
- `D01` [persistence] **PASS** (66.3158s) restart_after_setup
- `D02` [persistence] **PASS** (109.5705s) restart_after_setup
- `D03` [persistence] **PASS** (62.8522s) restart_after_setup
- `D04` [persistence] **FAIL** (58.7783s) restart_after_setup
- `D05` [persistence] **PASS** (58.4329s) restart_after_setup
- `E01` [long_task] **FAIL** (65.9163s) 
- `E02` [long_task] **FAIL** (124.4374s) 
- `E03` [long_task] **FAIL** (124.1494s) 
- `E04` [long_task] **PASS** (152.4846s) 
- `E05` [long_task] **PASS** (118.0732s) 
- `F01` [truthfulness] **PASS** (0.0087s) 
- `F02` [truthfulness] **PASS** (0.0091s) 
- `F03` [truthfulness] **PASS** (0.0136s) 
- `F04` [truthfulness] **PASS** (0.0122s) 
- `F05` [truthfulness] **PASS** (0.0124s) 
