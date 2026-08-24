# Run idos-20260819T045709Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T05:49:33.943893+00:00`
- tasks completed: `30`
- success: `5/30` (17%)
- hallucination: `4/30` (13%)
- avg latency: `91.4707s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 0/5 (0%) | 0/5 (0%) | 63.7384s |
| memory | 1/5 (20%) | 0/5 (0%) | 109.5708s |
| persistence | 0/5 (0%) | 0/5 (0%) | 110.2596s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 53.9539s |
| tools | 0/5 (0%) | 0/5 (0%) | 49.1476s |
| truthfulness | 1/5 (20%) | 4/5 (80%) | 162.1538s |

## Tasks

- `A01` [reasoning] **PASS** (25.1613s) 
- `A02` [reasoning] **PASS** (12.4989s) 
- `A03` [reasoning] **PASS** (10.4453s) 
- `A04` [reasoning] **FAIL** (11.6964s) 
- `A05` [reasoning] **FAIL** (209.9676s) 
- `B01` [memory] **PASS** (63.6861s) 
- `B02` [memory] **FAIL** (87.5381s) 
- `B03` [memory] **FAIL** (99.748s) 
- `B04` [memory] **FAIL** (176.3338s) 
- `B05` [memory] **FAIL** (120.5482s) 
- `C01` [tools] **FAIL** (40.2788s) 
- `C02` [tools] **FAIL** (47.9057s) 
- `C03` [tools] **FAIL** (59.6488s) 
- `C04` [tools] **FAIL** (53.0373s) 
- `C05` [tools] **FAIL** (44.8673s) 
- `D01` [persistence] **FAIL** (123.8446s) restart_after_setup
- `D02` [persistence] **FAIL** (120.1844s) restart_after_setup
- `D03` [persistence] **FAIL** (127.4504s) restart_after_setup
- `D04` [persistence] **FAIL** (91.9033s) restart_after_setup
- `D05` [persistence] **FAIL** (87.9151s) restart_after_setup
- `E01` [long_task] **FAIL** (44.8895s) 
- `E02` [long_task] **FAIL** (46.386s) 
- `E03` [long_task] **FAIL** (92.7575s) 
- `E04` [long_task] **FAIL** (45.963s) 
- `E05` [long_task] **FAIL** (88.6959s) 
- `F01` [truthfulness] **FAIL** HALLUCINATION (45.1691s) 
- `F02` [truthfulness] **FAIL** HALLUCINATION (45.3072s) 
- `F03` [truthfulness] **FAIL** HALLUCINATION (631.4464s) 
- `F04` [truthfulness] **FAIL** HALLUCINATION (42.1185s) 
- `F05` [truthfulness] **PASS** (46.728s) 
