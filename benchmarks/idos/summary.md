# Run idos-20260819T174343Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T18:12:24.974019+00:00`
- tasks completed: `30`
- success: `15/30` (50%)
- hallucination: `0/30` (0%)
- avg latency: `57.3604s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 2/5 (40%) | 0/5 (0%) | 65.0524s |
| memory | 3/5 (60%) | 0/5 (0%) | 84.4517s |
| persistence | 0/5 (0%) | 0/5 (0%) | 85.5572s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 15.1686s |
| tools | 1/5 (20%) | 0/5 (0%) | 49.9015s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 44.031s |

## Tasks

- `A01` [reasoning] **PASS** (26.9459s) 
- `A02` [reasoning] **PASS** (12.5356s) 
- `A03` [reasoning] **PASS** (10.7705s) 
- `A04` [reasoning] **PASS** (11.423s) 
- `A05` [reasoning] **FAIL** (14.1679s) 
- `B01` [memory] **FAIL** (50.602s) 
- `B02` [memory] **PASS** (68.8012s) 
- `B03` [memory] **PASS** (85.5262s) 
- `B04` [memory] **PASS** (135.1408s) 
- `B05` [memory] **FAIL** (82.1882s) 
- `C01` [tools] **FAIL** (49.6267s) 
- `C02` [tools] **FAIL** (72.3486s) 
- `C03` [tools] **PASS** (41.2258s) 
- `C04` [tools] **FAIL** (42.6125s) 
- `C05` [tools] **FAIL** (43.6937s) 
- `D01` [persistence] **FAIL** (86.5364s) restart_after_setup
- `D02` [persistence] **FAIL** (85.005s) restart_after_setup
- `D03` [persistence] **FAIL** (89.3294s) restart_after_setup
- `D04` [persistence] **FAIL** (83.3463s) restart_after_setup
- `D05` [persistence] **FAIL** (83.5688s) restart_after_setup
- `E01` [long_task] **FAIL** (43.2864s) 
- `E02` [long_task] **FAIL** (42.6283s) 
- `E03` [long_task] **PASS** (90.0519s) 
- `E04` [long_task] **PASS** (50.3331s) 
- `E05` [long_task] **FAIL** (98.9622s) 
- `F01` [truthfulness] **PASS** (43.9274s) 
- `F02` [truthfulness] **PASS** (42.8288s) 
- `F03` [truthfulness] **PASS** (43.6263s) 
- `F04` [truthfulness] **PASS** (44.2421s) 
- `F05` [truthfulness] **PASS** (45.5305s) 
