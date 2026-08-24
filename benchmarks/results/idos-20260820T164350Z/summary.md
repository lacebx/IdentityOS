# Run idos-20260820T164350Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-20T17:07:48.192595+00:00`
- tasks completed: `30`
- success: `23/30` (77%)
- hallucination: `0/30` (0%)
- avg latency: `47.8813s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 73.9446s |
| memory | 5/5 (100%) | 0/5 (0%) | 79.4087s |
| persistence | 4/5 (80%) | 0/5 (0%) | 48.2627s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.2565s |
| tools | 3/5 (60%) | 0/5 (0%) | 70.4068s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0086s |

## Tasks

- `A01` [reasoning] **PASS** (26.6818s) 
- `A02` [reasoning] **PASS** (11.8367s) 
- `A03` [reasoning] **PASS** (11.119s) 
- `A04` [reasoning] **PASS** (11.9848s) 
- `A05` [reasoning] **FAIL** (14.6602s) 
- `B01` [memory] **PASS** (20.0439s) 
- `B02` [memory] **PASS** (25.3951s) 
- `B03` [memory] **PASS** (45.1731s) 
- `B04` [memory] **PASS** (174.5355s) 
- `B05` [memory] **PASS** (131.8959s) 
- `C01` [tools] **FAIL** (58.2207s) 
- `C02` [tools] **FAIL** (106.4313s) 
- `C03` [tools] **PASS** (71.4831s) 
- `C04` [tools] **PASS** (55.3206s) 
- `C05` [tools] **PASS** (60.5784s) 
- `D01` [persistence] **PASS** (52.8303s) restart_after_setup
- `D02` [persistence] **PASS** (47.4309s) restart_after_setup
- `D03` [persistence] **PASS** (45.9004s) restart_after_setup
- `D04` [persistence] **FAIL** (46.6479s) restart_after_setup
- `D05` [persistence] **PASS** (48.5042s) restart_after_setup
- `E01` [long_task] **FAIL** (46.0545s) 
- `E02` [long_task] **FAIL** (51.2185s) 
- `E03` [long_task] **FAIL** (94.6262s) 
- `E04` [long_task] **PASS** (62.8337s) 
- `E05` [long_task] **PASS** (114.9899s) 
- `F01` [truthfulness] **PASS** (0.0202s) 
- `F02` [truthfulness] **PASS** (0.0057s) 
- `F03` [truthfulness] **PASS** (0.0055s) 
- `F04` [truthfulness] **PASS** (0.0045s) 
- `F05` [truthfulness] **PASS** (0.0073s) 
