# Run idos-20260824T062518Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T06:46:57.330916+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `43.2225s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 3/5 (60%) | 0/5 (0%) | 70.6175s |
| memory | 4/5 (80%) | 0/5 (0%) | 66.6462s |
| persistence | 4/5 (80%) | 0/5 (0%) | 50.0733s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 24.6703s |
| tools | 1/5 (20%) | 0/5 (0%) | 47.3056s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0224s |

## Tasks

- `A01` [reasoning] **PASS** (63.7421s) 
- `A02` [reasoning] **PASS** (18.8158s) 
- `A03` [reasoning] **PASS** (11.7918s) 
- `A04` [reasoning] **PASS** (13.089s) 
- `A05` [reasoning] **FAIL** (15.9127s) 
- `B01` [memory] **PASS** (55.1947s) 
- `B02` [memory] **PASS** (44.3159s) 
- `B03` [memory] **PASS** (44.6608s) 
- `B04` [memory] **FAIL** (145.1948s) 
- `B05` [memory] **PASS** (43.8646s) 
- `C01` [tools] **FAIL** (48.5488s) 
- `C02` [tools] **FAIL** (60.2515s) 
- `C03` [tools] **PASS** (41.0529s) 
- `C04` [tools] **FAIL** (46.6768s) 
- `C05` [tools] **FAIL** (39.9979s) 
- `D01` [persistence] **PASS** (46.5421s) restart_after_setup
- `D02` [persistence] **PASS** (58.6271s) restart_after_setup
- `D03` [persistence] **PASS** (50.4097s) restart_after_setup
- `D04` [persistence] **FAIL** (49.6095s) restart_after_setup
- `D05` [persistence] **PASS** (45.178s) restart_after_setup
- `E01` [long_task] **FAIL** (43.9059s) 
- `E02` [long_task] **FAIL** (44.0724s) 
- `E03` [long_task] **PASS** (100.2306s) 
- `E04` [long_task] **PASS** (57.7065s) 
- `E05` [long_task] **PASS** (107.1723s) 
- `F01` [truthfulness] **PASS** (0.0576s) 
- `F02` [truthfulness] **PASS** (0.0115s) 
- `F03` [truthfulness] **PASS** (0.0147s) 
- `F04` [truthfulness] **PASS** (0.0132s) 
- `F05` [truthfulness] **PASS** (0.0152s) 
