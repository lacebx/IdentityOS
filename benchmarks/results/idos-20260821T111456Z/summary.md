# Run idos-20260821T111456Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T11:34:00.150991+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `38.1021s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 58.8556s |
| memory | 5/5 (100%) | 0/5 (0%) | 64.8187s |
| persistence | 4/5 (80%) | 0/5 (0%) | 46.1219s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 16.5613s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.2471s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.008s |

## Tasks

- `A01` [reasoning] **PASS** (34.1021s) 
- `A02` [reasoning] **PASS** (12.1509s) 
- `A03` [reasoning] **FAIL** (10.3795s) 
- `A04` [reasoning] **PASS** (11.7995s) 
- `A05` [reasoning] **FAIL** (14.3745s) 
- `B01` [memory] **PASS** (22.6409s) 
- `B02` [memory] **PASS** (26.6374s) 
- `B03` [memory] **PASS** (40.4719s) 
- `B04` [memory] **PASS** (191.5005s) 
- `B05` [memory] **PASS** (42.843s) 
- `C01` [tools] **FAIL** (40.9836s) 
- `C02` [tools] **FAIL** (41.9869s) 
- `C03` [tools] **PASS** (42.1237s) 
- `C04` [tools] **FAIL** (40.9026s) 
- `C05` [tools] **FAIL** (45.2386s) 
- `D01` [persistence] **PASS** (46.3068s) restart_after_setup
- `D02` [persistence] **PASS** (49.0627s) restart_after_setup
- `D03` [persistence] **PASS** (46.3413s) restart_after_setup
- `D04` [persistence] **FAIL** (44.1113s) restart_after_setup
- `D05` [persistence] **PASS** (44.7876s) restart_after_setup
- `E01` [long_task] **FAIL** (46.0104s) 
- `E02` [long_task] **FAIL** (49.8293s) 
- `E03` [long_task] **FAIL** (46.2741s) 
- `E04` [long_task] **PASS** (43.9444s) 
- `E05` [long_task] **PASS** (108.2199s) 
- `F01` [truthfulness] **PASS** (0.0087s) 
- `F02` [truthfulness] **PASS** (0.0102s) 
- `F03` [truthfulness] **PASS** (0.0072s) 
- `F04` [truthfulness] **PASS** (0.0074s) 
- `F05` [truthfulness] **PASS** (0.0063s) 
