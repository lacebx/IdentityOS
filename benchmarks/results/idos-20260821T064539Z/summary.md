# Run idos-20260821T064539Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T07:10:05.300997+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `48.829s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 93.1894s |
| memory | 5/5 (100%) | 0/5 (0%) | 75.9711s |
| persistence | 4/5 (80%) | 0/5 (0%) | 49.2735s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 18.5983s |
| tools | 2/5 (40%) | 0/5 (0%) | 55.9325s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0093s |

## Tasks

- `A01` [reasoning] **PASS** (32.9206s) 
- `A02` [reasoning] **PASS** (11.5509s) 
- `A03` [reasoning] **FAIL** (13.2515s) 
- `A04` [reasoning] **PASS** (15.6559s) 
- `A05` [reasoning] **FAIL** (19.6128s) 
- `B01` [memory] **PASS** (29.2741s) 
- `B02` [memory] **PASS** (48.6064s) 
- `B03` [memory] **PASS** (58.285s) 
- `B04` [memory] **PASS** (183.6636s) 
- `B05` [memory] **PASS** (60.0266s) 
- `C01` [tools] **FAIL** (58.6713s) 
- `C02` [tools] **FAIL** (61.8748s) 
- `C03` [tools] **FAIL** (61.0393s) 
- `C04` [tools] **PASS** (48.9889s) 
- `C05` [tools] **PASS** (49.0882s) 
- `D01` [persistence] **PASS** (52.1311s) restart_after_setup
- `D02` [persistence] **PASS** (53.1741s) restart_after_setup
- `D03` [persistence] **PASS** (54.4874s) restart_after_setup
- `D04` [persistence] **FAIL** (44.7255s) restart_after_setup
- `D05` [persistence] **PASS** (41.8493s) restart_after_setup
- `E01` [long_task] **FAIL** (45.1093s) 
- `E02` [long_task] **FAIL** (46.997s) 
- `E03` [long_task] **PASS** (92.1605s) 
- `E04` [long_task] **PASS** (114.9231s) 
- `E05` [long_task] **FAIL** (166.7572s) 
- `F01` [truthfulness] **PASS** (0.011s) 
- `F02` [truthfulness] **PASS** (0.0075s) 
- `F03` [truthfulness] **PASS** (0.0115s) 
- `F04` [truthfulness] **PASS** (0.0064s) 
- `F05` [truthfulness] **PASS** (0.0102s) 
