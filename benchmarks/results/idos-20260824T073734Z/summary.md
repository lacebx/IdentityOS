# Run idos-20260824T073734Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T07:58:38.811755+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `42.1397s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 68.5339s |
| memory | 5/5 (100%) | 0/5 (0%) | 71.5179s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.7162s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 18.3688s |
| tools | 3/5 (60%) | 0/5 (0%) | 46.6853s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0162s |

## Tasks

- `A01` [reasoning] **PASS** (35.8842s) 
- `A02` [reasoning] **PASS** (18.4112s) 
- `A03` [reasoning] **FAIL** (11.527s) 
- `A04` [reasoning] **PASS** (11.5687s) 
- `A05` [reasoning] **FAIL** (14.4531s) 
- `B01` [memory] **PASS** (21.9172s) 
- `B02` [memory] **PASS** (45.6909s) 
- `B03` [memory] **PASS** (44.9199s) 
- `B04` [memory] **PASS** (168.2983s) 
- `B05` [memory] **PASS** (76.7632s) 
- `C01` [tools] **FAIL** (55.7342s) 
- `C02` [tools] **FAIL** (45.437s) 
- `C03` [tools] **PASS** (43.4761s) 
- `C04` [tools] **PASS** (43.4945s) 
- `C05` [tools] **PASS** (45.2847s) 
- `D01` [persistence] **PASS** (45.7137s) restart_after_setup
- `D02` [persistence] **PASS** (49.0211s) restart_after_setup
- `D03` [persistence] **PASS** (45.6435s) restart_after_setup
- `D04` [persistence] **FAIL** (45.3151s) restart_after_setup
- `D05` [persistence] **PASS** (52.8876s) restart_after_setup
- `E01` [long_task] **FAIL** (44.2799s) 
- `E02` [long_task] **FAIL** (47.5547s) 
- `E03` [long_task] **FAIL** (98.2658s) 
- `E04` [long_task] **FAIL** (51.7278s) 
- `E05` [long_task] **FAIL** (100.8414s) 
- `F01` [truthfulness] **PASS** (0.02s) 
- `F02` [truthfulness] **PASS** (0.0101s) 
- `F03` [truthfulness] **PASS** (0.0246s) 
- `F04` [truthfulness] **PASS** (0.013s) 
- `F05` [truthfulness] **PASS** (0.0132s) 
