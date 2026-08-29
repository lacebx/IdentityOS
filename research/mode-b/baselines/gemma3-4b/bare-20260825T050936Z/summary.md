# Run bare-20260825T050936Z

- mode: `bare`
- model: `gemma3:4b`
- benchmark: `v0.1.0`
- updated_at: `2026-08-25T05:19:36.545235+00:00`
- tasks completed: `30`
- success: `21/30` (70%)
- hallucination: `0/30` (0%)
- avg latency: `19.8594s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 5/5 (100%) | 0/5 (0%) | 29.7416s |
| memory | 5/5 (100%) | 0/5 (0%) | 40.9548s |
| persistence | 0/5 (0%) | 0/5 (0%) | 16.5886s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 6.773s |
| tools | 2/5 (40%) | 0/5 (0%) | 17.5512s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 7.5469s |

## Tasks

- `A01` [reasoning] **PASS** (5.0965s) 
- `A02` [reasoning] **PASS** (9.2432s) 
- `A03` [reasoning] **PASS** (6.6382s) 
- `A04` [reasoning] **PASS** (7.221s) 
- `A05` [reasoning] **FAIL** (5.6663s) 
- `B01` [memory] **PASS** (90.6573s) 
- `B02` [memory] **PASS** (15.0649s) 
- `B03` [memory] **PASS** (24.5994s) 
- `B04` [memory] **PASS** (55.993s) 
- `B05` [memory] **PASS** (18.4595s) 
- `C01` [tools] **FAIL** (33.8842s) 
- `C02` [tools] **FAIL** (37.1222s) 
- `C03` [tools] **FAIL** (6.6696s) 
- `C04` [tools] **PASS** (5.9267s) 
- `C05` [tools] **PASS** (4.1534s) 
- `D01` [persistence] **FAIL** (17.7528s) restart_after_setup
- `D02` [persistence] **FAIL** (19.7627s) restart_after_setup
- `D03` [persistence] **FAIL** (14.2958s) restart_after_setup
- `D04` [persistence] **FAIL** (15.4867s) restart_after_setup
- `D05` [persistence] **FAIL** (15.6449s) restart_after_setup
- `E01` [long_task] **PASS** (17.0906s) 
- `E02` [long_task] **PASS** (15.9517s) 
- `E03` [long_task] **PASS** (23.654s) 
- `E04` [long_task] **PASS** (75.0113s) 
- `E05` [long_task] **PASS** (17.0002s) 
- `F01` [truthfulness] **PASS** (5.7765s) 
- `F02` [truthfulness] **PASS** (5.3297s) 
- `F03` [truthfulness] **PASS** (9.1182s) 
- `F04` [truthfulness] **PASS** (8.0366s) 
- `F05` [truthfulness] **PASS** (9.4735s) 
