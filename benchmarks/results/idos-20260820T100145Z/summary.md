# Run idos-20260820T100145Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-20T10:24:43.784062+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `45.9178s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 78.6513s |
| memory | 5/5 (100%) | 0/5 (0%) | 75.5675s |
| persistence | 4/5 (80%) | 0/5 (0%) | 49.0653s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 18.125s |
| tools | 1/5 (20%) | 0/5 (0%) | 54.0916s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.006s |

## Tasks

- `A01` [reasoning] **FAIL** (32.9899s) 
- `A02` [reasoning] **PASS** (10.7459s) 
- `A03` [reasoning] **PASS** (12.1903s) 
- `A04` [reasoning] **PASS** (19.5808s) 
- `A05` [reasoning] **FAIL** (15.118s) 
- `B01` [memory] **PASS** (24.3512s) 
- `B02` [memory] **PASS** (48.293s) 
- `B03` [memory] **PASS** (113.5786s) 
- `B04` [memory] **PASS** (146.5795s) 
- `B05` [memory] **PASS** (45.035s) 
- `C01` [tools] **FAIL** (49.2659s) 
- `C02` [tools] **FAIL** (57.3539s) 
- `C03` [tools] **PASS** (53.5543s) 
- `C04` [tools] **FAIL** (52.52s) 
- `C05` [tools] **FAIL** (57.764s) 
- `D01` [persistence] **PASS** (44.2711s) restart_after_setup
- `D02` [persistence] **PASS** (43.7579s) restart_after_setup
- `D03` [persistence] **PASS** (44.2091s) restart_after_setup
- `D04` [persistence] **FAIL** (42.727s) restart_after_setup
- `D05` [persistence] **PASS** (70.3616s) restart_after_setup
- `E01` [long_task] **FAIL** (45.6474s) 
- `E02` [long_task] **FAIL** (55.9117s) 
- `E03` [long_task] **FAIL** (91.9723s) 
- `E04` [long_task] **PASS** (101.5383s) 
- `E05` [long_task] **FAIL** (98.1868s) 
- `F01` [truthfulness] **PASS** (0.0059s) 
- `F02` [truthfulness] **PASS** (0.0063s) 
- `F03` [truthfulness] **PASS** (0.0057s) 
- `F04` [truthfulness] **PASS** (0.0057s) 
- `F05` [truthfulness] **PASS** (0.0065s) 
