# Run idos-20260821T152236Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T15:39:26.295154+00:00`
- tasks completed: `30`
- success: `19/30` (63%)
- hallucination: `0/30` (0%)
- avg latency: `33.4926s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| long_task | 1/5 (20%) | 0/5 (0%) | 28.9952s |
| memory | 5/5 (100%) | 0/5 (0%) | 61.1883s |
| persistence | 4/5 (80%) | 0/5 (0%) | 48.4338s |
| reasoning | 3/5 (60%) | 0/5 (0%) | 18.3148s |
| tools | 1/5 (20%) | 0/5 (0%) | 44.0136s |
| truthfulness | 5/5 (100%) | 0/5 (0%) | 0.0096s |

## Tasks

- `A01` [reasoning] **PASS** (33.3232s) 
- `A02` [reasoning] **PASS** (17.7038s) 
- `A03` [reasoning] **PASS** (11.8235s) 
- `A04` [reasoning] **FAIL** (13.1207s) 
- `A05` [reasoning] **FAIL** (15.6028s) 
- `B01` [memory] **PASS** (32.0521s) 
- `B02` [memory] **PASS** (43.4217s) 
- `B03` [memory] **PASS** (42.0663s) 
- `B04` [memory] **PASS** (143.2815s) 
- `B05` [memory] **PASS** (45.1201s) 
- `C01` [tools] **FAIL** (42.7307s) 
- `C02` [tools] **FAIL** (44.44s) 
- `C03` [tools] **PASS** (42.9601s) 
- `C04` [tools] **FAIL** (45.6262s) 
- `C05` [tools] **FAIL** (44.3111s) 
- `D01` [persistence] **PASS** (50.9392s) restart_after_setup
- `D02` [persistence] **PASS** (57.5665s) restart_after_setup
- `D03` [persistence] **PASS** (44.5005s) restart_after_setup
- `D04` [persistence] **FAIL** (43.6149s) restart_after_setup
- `D05` [persistence] **PASS** (45.5481s) restart_after_setup
- `E01` [long_task] **FAIL** (46.9856s) 
- `E02` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E03` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E04` [long_task] **FAIL** (0.0s) error:RuntimeError: Adapter error (model='smollm2:360m-instruct-q4_0', base_url='http://localhost:11434/v1'): Connection error.
- `E05` [long_task] **PASS** (97.9902s) 
- `F01` [truthfulness] **PASS** (0.0073s) 
- `F02` [truthfulness] **PASS** (0.0222s) 
- `F03` [truthfulness] **PASS** (0.0071s) 
- `F04` [truthfulness] **PASS** (0.006s) 
- `F05` [truthfulness] **PASS** (0.0054s) 
