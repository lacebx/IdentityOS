# Run bare-20260819T045600Z

- mode: `bare`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T04:57:01.479785+00:00`
- tasks completed: `30`
- success: `11/30` (37%)
- hallucination: `2/30` (7%)
- avg latency: `2.0249s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 2.1866s |
| memory | 3/5 (60%) | 0/5 (0%) | 3.9187s |
| persistence | 0/5 (0%) | 0/5 (0%) | 2.0739s |
| reasoning | 2/5 (40%) | 0/5 (0%) | 1.6021s |
| tools | 2/5 (40%) | 0/5 (0%) | 1.2224s |
| truthfulness | 3/5 (60%) | 2/5 (40%) | 1.1456s |

## Tasks

- `A01` [reasoning] **FAIL** (5.695s) 
- `A02` [reasoning] **PASS** (0.9161s) 
- `A03` [reasoning] **PASS** (0.5231s) 
- `A04` [reasoning] **FAIL** (0.4015s) 
- `A05` [reasoning] **FAIL** (0.4749s) 
- `B01` [memory] **PASS** (2.3314s) 
- `B02` [memory] **PASS** (1.2068s) 
- `B03` [memory] **FAIL** (3.042s) 
- `B04` [memory] **PASS** (9.5234s) 
- `B05` [memory] **FAIL** (3.4898s) 
- `C01` [tools] **FAIL** (1.9189s) 
- `C02` [tools] **FAIL** (2.6235s) 
- `C03` [tools] **FAIL** (0.4846s) 
- `C04` [tools] **PASS** (0.5755s) 
- `C05` [tools] **PASS** (0.5094s) 
- `D01` [persistence] **FAIL** (1.8096s) restart_after_setup
- `D02` [persistence] **FAIL** (0.9072s) restart_after_setup
- `D03` [persistence] **FAIL** (1.6303s) restart_after_setup
- `D04` [persistence] **FAIL** (3.0088s) restart_after_setup
- `D05` [persistence] **FAIL** (3.0134s) restart_after_setup
- `E01` [long_task] **FAIL** (1.4305s) 
- `E02` [long_task] **FAIL** (2.499s) 
- `E03` [long_task] **FAIL** (2.1806s) 
- `E04` [long_task] **PASS** (1.602s) 
- `E05` [long_task] **FAIL** (3.2211s) 
- `F01` [truthfulness] **FAIL** HALLUCINATION (0.7126s) 
- `F02` [truthfulness] **FAIL** HALLUCINATION (1.042s) 
- `F03` [truthfulness] **PASS** (1.7183s) 
- `F04` [truthfulness] **PASS** (0.4118s) 
- `F05` [truthfulness] **PASS** (1.8431s) 
