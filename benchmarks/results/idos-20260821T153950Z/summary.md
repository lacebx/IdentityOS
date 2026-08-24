# Run idos-20260821T153950Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T15:59:06.452258+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `38.5127s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 66.6088s |
| memory | 5/5 (100%) | 0/5 (0%) | 59.5901s |
| persistence | 4/5 (80%) | 0/5 (0%) | 44.1235s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 17.8015s |
| tools | 1/5 (20%) | 0/5 (0%) | 42.9337s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0186s |

## Tasks

- `A01` [reasoning] **PASS** (25.9514s) 
- `A02` [reasoning] **PASS** (11.1936s) 
- `A03` [reasoning] **PASS** (12.4627s) 
- `A04` [reasoning] **PASS** (19.4671s) 
- `A05` [reasoning] **FAIL** (19.9329s) 
- `B01` [memory] **PASS** (23.3712s) 
- `B02` [memory] **PASS** (40.5528s) 
- `B03` [memory] **PASS** (42.9643s) 
- `B04` [memory] **PASS** (146.9495s) 
- `B05` [memory] **PASS** (44.1129s) 
- `C01` [tools] **FAIL** (41.206s) 
- `C02` [tools] **FAIL** (43.9657s) 
- `C03` [tools] **FAIL** (45.4359s) 
- `C04` [tools] **FAIL** (43.4696s) 
- `C05` [tools] **PASS** (40.5911s) 
- `D01` [persistence] **PASS** (41.2906s) restart_after_setup
- `D02` [persistence] **PASS** (47.4502s) restart_after_setup
- `D03` [persistence] **PASS** (41.9302s) restart_after_setup
- `D04` [persistence] **FAIL** (45.2349s) restart_after_setup
- `D05` [persistence] **PASS** (44.7114s) restart_after_setup
- `E01` [long_task] **FAIL** (41.8751s) 
- `E02` [long_task] **FAIL** (50.4125s) 
- `E03` [long_task] **FAIL** (87.8699s) 
- `E04` [long_task] **PASS** (61.7994s) 
- `E05` [long_task] **PASS** (91.0869s) 
- `F01` [truthfulness] **PASS** (0.0078s) 
- `F02` [truthfulness] **PASS** (0.0217s) 
- `F03` [truthfulness] **PASS** (0.0078s) 
- `F04` [truthfulness] **PASS** (0.0146s) 
- `F05` [truthfulness] **PASS** (0.0412s) 
