# Run idos-20260821T085202Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T09:03:46.787645+00:00`
- tasks completed: `17`
- success: `12/17` (71%)
- hallucination: `0/17` (0%)
- avg latency: `41.3769s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 5/5 (100%) | 0/5 (0%) | 65.0029s |
| persistence | 2/2 (100%) | 0/2 (0%) | 45.857s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 13.7763s |
| tools | 2/5 (40%) | 0/5 (0%) | 43.5596s |

## Tasks

- `A01` [reasoning] **PASS** (16.9768s) 
- `A02` [reasoning] **PASS** (13.5399s) 
- `A03` [reasoning] **PASS** (11.1148s) 
- `A04` [reasoning] **FAIL** (11.7171s) 
- `A05` [reasoning] **FAIL** (15.5329s) 
- `B01` [memory] **PASS** (24.0896s) 
- `B02` [memory] **PASS** (46.5907s) 
- `B03` [memory] **PASS** (43.8994s) 
- `B04` [memory] **PASS** (167.1359s) 
- `B05` [memory] **PASS** (43.2991s) 
- `C01` [tools] **FAIL** (43.2016s) 
- `C02` [tools] **FAIL** (44.5692s) 
- `C03` [tools] **PASS** (44.5737s) 
- `C04` [tools] **PASS** (41.5537s) 
- `C05` [tools] **FAIL** (43.8996s) 
- `D01` [persistence] **PASS** (45.3805s) restart_after_setup
- `D02` [persistence] **PASS** (46.3335s) restart_after_setup
