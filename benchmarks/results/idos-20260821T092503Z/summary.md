# Run idos-20260821T092503Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T09:58:52.411678+00:00`
- tasks completed: `30`
- success: `22/30` (73%)
- hallucination: `0/30` (0%)
- avg latency: `67.6075s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 224.1675s |
| memory | 5/5 (100%) | 0/5 (0%) | 70.2805s |
| persistence | 4/5 (80%) | 0/5 (0%) | 47.6883s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 19.193s |
| tools | 3/5 (60%) | 0/5 (0%) | 44.3078s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0079s |

## Tasks

- `A01` [reasoning] **PASS** (47.1362s) 
- `A02` [reasoning] **PASS** (11.8392s) 
- `A03` [reasoning] **FAIL** (11.1284s) 
- `A04` [reasoning] **PASS** (11.8842s) 
- `A05` [reasoning] **FAIL** (13.9771s) 
- `B01` [memory] **PASS** (87.915s) 
- `B02` [memory] **PASS** (43.4819s) 
- `B03` [memory] **PASS** (42.9043s) 
- `B04` [memory] **PASS** (134.8302s) 
- `B05` [memory] **PASS** (42.2712s) 
- `C01` [tools] **FAIL** (42.9389s) 
- `C02` [tools] **FAIL** (46.1332s) 
- `C03` [tools] **PASS** (44.6314s) 
- `C04` [tools] **PASS** (43.81s) 
- `C05` [tools] **PASS** (44.0254s) 
- `D01` [persistence] **PASS** (43.1581s) restart_after_setup
- `D02` [persistence] **PASS** (46.7855s) restart_after_setup
- `D03` [persistence] **PASS** (48.4531s) restart_after_setup
- `D04` [persistence] **FAIL** (47.9246s) restart_after_setup
- `D05` [persistence] **PASS** (52.12s) restart_after_setup
- `E01` [long_task] **FAIL** (45.9951s) 
- `E02` [long_task] **FAIL** (808.3768s) 
- `E03` [long_task] **PASS** (56.0891s) 
- `E04` [long_task] **PASS** (71.7587s) 
- `E05` [long_task] **FAIL** (138.6178s) 
- `F01` [truthfulness] **PASS** (0.0091s) 
- `F02` [truthfulness] **PASS** (0.0098s) 
- `F03` [truthfulness] **PASS** (0.0068s) 
- `F04` [truthfulness] **PASS** (0.0066s) 
- `F05` [truthfulness] **PASS** (0.0071s) 
