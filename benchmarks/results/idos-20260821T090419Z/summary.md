# Run idos-20260821T090419Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T09:24:17.227321+00:00`
- tasks completed: `30`
- success: `20/30` (67%)
- hallucination: `0/30` (0%)
- avg latency: `39.8418s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 65.1865s |
| memory | 4/5 (80%) | 0/5 (0%) | 59.5565s |
| persistence | 4/5 (80%) | 0/5 (0%) | 44.5987s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 19.0329s |
| tools | 1/5 (20%) | 0/5 (0%) | 50.5972s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0789s |

## Tasks

- `A01` [reasoning] **PASS** (38.6663s) 
- `A02` [reasoning] **PASS** (12.7274s) 
- `A03` [reasoning] **PASS** (14.4248s) 
- `A04` [reasoning] **PASS** (14.124s) 
- `A05` [reasoning] **FAIL** (15.2221s) 
- `B01` [memory] **PASS** (21.8432s) 
- `B02` [memory] **PASS** (44.6704s) 
- `B03` [memory] **PASS** (43.4515s) 
- `B04` [memory] **FAIL** (142.1338s) 
- `B05` [memory] **PASS** (45.6834s) 
- `C01` [tools] **FAIL** (43.496s) 
- `C02` [tools] **FAIL** (82.5212s) 
- `C03` [tools] **PASS** (43.2267s) 
- `C04` [tools] **FAIL** (41.2013s) 
- `C05` [tools] **FAIL** (42.5406s) 
- `D01` [persistence] **PASS** (48.5672s) restart_after_setup
- `D02` [persistence] **PASS** (41.2415s) restart_after_setup
- `D03` [persistence] **PASS** (41.4244s) restart_after_setup
- `D04` [persistence] **FAIL** (44.2614s) restart_after_setup
- `D05` [persistence] **PASS** (47.4989s) restart_after_setup
- `E01` [long_task] **FAIL** (41.5169s) 
- `E02` [long_task] **FAIL** (55.9627s) 
- `E03` [long_task] **FAIL** (90.004s) 
- `E04` [long_task] **PASS** (47.1809s) 
- `E05` [long_task] **PASS** (91.2682s) 
- `F01` [truthfulness] **PASS** (0.0073s) 
- `F02` [truthfulness] **PASS** (0.2411s) 
- `F03` [truthfulness] **PASS** (0.1283s) 
- `F04` [truthfulness] **PASS** (0.0112s) 
- `F05` [truthfulness] **PASS** (0.0065s) 
