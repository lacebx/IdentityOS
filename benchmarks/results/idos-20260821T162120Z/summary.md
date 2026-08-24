# Run idos-20260821T162120Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T16:40:31.656941+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `38.356s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 71.4654s |
| memory | 5/5 (100%) | 0/5 (0%) | 58.9798s |
| persistence | 4/5 (80%) | 0/5 (0%) | 42.4827s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.1734s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.0209s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.014s |

## Tasks

- `A01` [reasoning] **PASS** (27.8034s) 
- `A02` [reasoning] **PASS** (11.0979s) 
- `A03` [reasoning] **PASS** (10.6416s) 
- `A04` [reasoning] **PASS** (11.5543s) 
- `A05` [reasoning] **FAIL** (14.7698s) 
- `B01` [memory] **PASS** (22.5517s) 
- `B02` [memory] **PASS** (26.5331s) 
- `B03` [memory] **PASS** (41.7151s) 
- `B04` [memory] **PASS** (159.3923s) 
- `B05` [memory] **PASS** (44.7068s) 
- `C01` [tools] **FAIL** (40.7691s) 
- `C02` [tools] **FAIL** (45.0339s) 
- `C03` [tools] **FAIL** (41.5823s) 
- `C04` [tools] **PASS** (40.9827s) 
- `C05` [tools] **FAIL** (41.7367s) 
- `D01` [persistence] **PASS** (40.4579s) restart_after_setup
- `D02` [persistence] **PASS** (40.4681s) restart_after_setup
- `D03` [persistence] **PASS** (49.1395s) restart_after_setup
- `D04` [persistence] **FAIL** (40.6587s) restart_after_setup
- `D05` [persistence] **PASS** (41.6893s) restart_after_setup
- `E01` [long_task] **FAIL** (50.1223s) 
- `E02` [long_task] **FAIL** (42.9452s) 
- `E03` [long_task] **FAIL** (101.8058s) 
- `E04` [long_task] **PASS** (61.453s) 
- `E05` [long_task] **PASS** (101.0006s) 
- `F01` [truthfulness] **PASS** (0.0232s) 
- `F02` [truthfulness] **PASS** (0.0098s) 
- `F03` [truthfulness] **PASS** (0.0077s) 
- `F04` [truthfulness] **PASS** (0.0094s) 
- `F05` [truthfulness] **PASS** (0.0201s) 
