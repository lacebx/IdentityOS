# Run idos-20260824T045138Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-24T05:39:50.214683+00:00`
- tasks completed: `30`
- success: `16/30` (53%)
- hallucination: `0/30` (0%)
- avg latency: `41.4223s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 80.4926s |
| memory | 5/5 (100%) | 0/5 (0%) | 56.1951s |
| persistence | 4/5 (80%) | 0/5 (0%) | 51.6234s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 16.9427s |
| tools | 0/5 (0%) | 0/5 (0%) | 43.2376s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0421s |

## Tasks

- `A01` [reasoning] **PASS** (36.9203s) 
- `A02` [reasoning] **PASS** (13.5859s) 
- `A03` [reasoning] **FAIL** (9.3177s) 
- `A04` [reasoning] **FAIL** (11.0935s) 
- `A05` [reasoning] **FAIL** (13.7962s) 
- `B01` [memory] **PASS** (26.9871s) 
- `B02` [memory] **PASS** (41.8712s) 
- `B03` [memory] **PASS** (45.5821s) 
- `B04` [memory] **PASS** (123.2658s) 
- `B05` [memory] **PASS** (43.2693s) 
- `C01` [tools] **FAIL** (38.0351s) 
- `C02` [tools] **FAIL** (52.0881s) 
- `C03` [tools] **FAIL** (41.574s) 
- `C04` [tools] **FAIL** (40.8792s) 
- `C05` [tools] **FAIL** (43.6118s) 
- `D01` [persistence] **PASS** (86.0476s) restart_after_setup
- `D02` [persistence] **PASS** (41.995s) restart_after_setup
- `D03` [persistence] **PASS** (39.8442s) restart_after_setup
- `D04` [persistence] **FAIL** (42.4497s) restart_after_setup
- `D05` [persistence] **PASS** (47.7807s) restart_after_setup
- `E01` [long_task] **FAIL** (46.6733s) 
- `E02` [long_task] **FAIL** (46.1366s) 
- `E03` [long_task] **FAIL** (97.9225s) 
- `E04` [long_task] **FAIL** (71.5467s) 
- `E05` [long_task] **FAIL** (140.1837s) 
- `F01` [truthfulness] **PASS** (0.0602s) 
- `F02` [truthfulness] **PASS** (0.0156s) 
- `F03` [truthfulness] **PASS** (0.0118s) 
- `F04` [truthfulness] **PASS** (0.084s) 
- `F05` [truthfulness] **PASS** (0.0391s) 
