# Run idos-20260821T142641Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T14:45:16.291497+00:00`
- tasks completed: `30`
- success: `17/30` (57%)
- hallucination: `0/30` (0%)
- avg latency: `37.1439s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 66.2921s |
| memory | 4/5 (80%) | 0/5 (0%) | 53.4346s |
| persistence | 4/5 (80%) | 0/5 (0%) | 45.898s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 14.7038s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.5285s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0066s |

## Tasks

- `A01` [reasoning] **PASS** (26.2489s) 
- `A02` [reasoning] **PASS** (11.1671s) 
- `A03` [reasoning] **FAIL** (10.2259s) 
- `A04` [reasoning] **PASS** (11.5455s) 
- `A05` [reasoning] **FAIL** (14.3315s) 
- `B01` [memory] **PASS** (22.0195s) 
- `B02` [memory] **PASS** (24.294s) 
- `B03` [memory] **PASS** (43.9889s) 
- `B04` [memory] **FAIL** (133.3674s) 
- `B05` [memory] **PASS** (43.5033s) 
- `C01` [tools] **FAIL** (44.8249s) 
- `C02` [tools] **FAIL** (44.4965s) 
- `C03` [tools] **PASS** (41.5352s) 
- `C04` [tools] **FAIL** (41.1444s) 
- `C05` [tools] **FAIL** (40.6413s) 
- `D01` [persistence] **PASS** (44.2477s) restart_after_setup
- `D02` [persistence] **PASS** (43.9309s) restart_after_setup
- `D03` [persistence] **PASS** (48.6423s) restart_after_setup
- `D04` [persistence] **FAIL** (46.8242s) restart_after_setup
- `D05` [persistence] **PASS** (45.8451s) restart_after_setup
- `E01` [long_task] **FAIL** (45.7103s) 
- `E02` [long_task] **FAIL** (49.0772s) 
- `E03` [long_task] **FAIL** (93.933s) 
- `E04` [long_task] **FAIL** (45.2586s) 
- `E05` [long_task] **FAIL** (97.4815s) 
- `F01` [truthfulness] **PASS** (0.0063s) 
- `F02` [truthfulness] **PASS** (0.0064s) 
- `F03` [truthfulness] **PASS** (0.0069s) 
- `F04` [truthfulness] **PASS** (0.0073s) 
- `F05` [truthfulness] **PASS** (0.0063s) 
