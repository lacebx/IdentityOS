# Run idos-20260824T070143Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T07:22:03.548961+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `40.5348s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 66.1102s |
| memory | 5/5 (100%) | 0/5 (0%) | 55.3659s |
| persistence | 4/5 (80%) | 0/5 (0%) | 50.3617s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 15.9268s |
| tools | 1/5 (20%) | 0/5 (0%) | 55.4287s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0157s |

## Tasks

- `A01` [reasoning] **PASS** (32.2208s) 
- `A02` [reasoning] **PASS** (10.9604s) 
- `A03` [reasoning] **FAIL** (10.2208s) 
- `A04` [reasoning] **PASS** (12.1696s) 
- `A05` [reasoning] **FAIL** (14.0626s) 
- `B01` [memory] **PASS** (20.8626s) 
- `B02` [memory] **PASS** (30.975s) 
- `B03` [memory] **PASS** (44.7715s) 
- `B04` [memory] **PASS** (135.4603s) 
- `B05` [memory] **PASS** (44.76s) 
- `C01` [tools] **FAIL** (41.2652s) 
- `C02` [tools] **FAIL** (67.1987s) 
- `C03` [tools] **FAIL** (57.709s) 
- `C04` [tools] **FAIL** (47.3305s) 
- `C05` [tools] **PASS** (63.6399s) 
- `D01` [persistence] **PASS** (74.9157s) restart_after_setup
- `D02` [persistence] **PASS** (43.397s) restart_after_setup
- `D03` [persistence] **PASS** (43.6307s) restart_after_setup
- `D04` [persistence] **FAIL** (43.6685s) restart_after_setup
- `D05` [persistence] **PASS** (46.1966s) restart_after_setup
- `E01` [long_task] **FAIL** (40.5728s) 
- `E02` [long_task] **FAIL** (48.3383s) 
- `E03` [long_task] **FAIL** (99.0144s) 
- `E04` [long_task] **PASS** (49.4053s) 
- `E05` [long_task] **FAIL** (93.2204s) 
- `F01` [truthfulness] **PASS** (0.0071s) 
- `F02` [truthfulness] **PASS** (0.0066s) 
- `F03` [truthfulness] **PASS** (0.0193s) 
- `F04` [truthfulness] **PASS** (0.0126s) 
- `F05` [truthfulness] **PASS** (0.0328s) 
