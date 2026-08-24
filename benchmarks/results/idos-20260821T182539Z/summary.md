# Run idos-20260821T182539Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T18:45:50.639349+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `40.3677s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 77.1647s |
| memory | 5/5 (100%) | 0/5 (0%) | 58.3341s |
| persistence | 4/5 (80%) | 0/5 (0%) | 44.3051s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 19.4948s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.8949s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0126s |

## Tasks

- `A01` [reasoning] **PASS** (42.6196s) 
- `A02` [reasoning] **PASS** (15.8492s) 
- `A03` [reasoning] **PASS** (11.4377s) 
- `A04` [reasoning] **PASS** (12.5556s) 
- `A05` [reasoning] **FAIL** (15.012s) 
- `B01` [memory] **PASS** (29.1017s) 
- `B02` [memory] **PASS** (42.6389s) 
- `B03` [memory] **PASS** (41.0898s) 
- `B04` [memory] **PASS** (131.124s) 
- `B05` [memory] **PASS** (47.7161s) 
- `C01` [tools] **FAIL** (43.7853s) 
- `C02` [tools] **FAIL** (42.7635s) 
- `C03` [tools] **FAIL** (44.2723s) 
- `C04` [tools] **FAIL** (42.3202s) 
- `C05` [tools] **PASS** (41.3333s) 
- `D01` [persistence] **PASS** (43.294s) restart_after_setup
- `D02` [persistence] **PASS** (42.7832s) restart_after_setup
- `D03` [persistence] **PASS** (43.5861s) restart_after_setup
- `D04` [persistence] **FAIL** (44.4384s) restart_after_setup
- `D05` [persistence] **PASS** (47.4239s) restart_after_setup
- `E01` [long_task] **FAIL** (43.7968s) 
- `E02` [long_task] **FAIL** (72.681s) 
- `E03` [long_task] **FAIL** (55.9857s) 
- `E04` [long_task] **PASS** (90.7908s) 
- `E05` [long_task] **FAIL** (122.5694s) 
- `F01` [truthfulness] **PASS** (0.0123s) 
- `F02` [truthfulness] **PASS** (0.0141s) 
- `F03` [truthfulness] **PASS** (0.0109s) 
- `F04` [truthfulness] **PASS** (0.013s) 
- `F05` [truthfulness] **PASS** (0.0126s) 
