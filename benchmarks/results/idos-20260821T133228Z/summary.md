# Run idos-20260821T133228Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-21T13:45:23.432969+00:00`
- tasks completed: `17`
- success: `11/17` (65%)
- hallucination: `0/17` (0%)
- avg latency: `45.5495s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| memory | 5/5 (100%) | 0/5 (0%) | 62.4649s |
| persistence | 2/2 (100%) | 0/2 (0%) | 47.6615s |
| reasoning | 4/5 (80%) | 0/5 (0%) | 16.4151s |
| tools | 0/5 (0%) | 0/5 (0%) | 56.9236s |

## Tasks

- `A01` [reasoning] **PASS** (27.8357s) 
- `A02` [reasoning] **PASS** (10.8316s) 
- `A03` [reasoning] **PASS** (10.121s) 
- `A04` [reasoning] **PASS** (11.6073s) 
- `A05` [reasoning] **FAIL** (21.6797s) 
- `B01` [memory] **PASS** (23.3487s) 
- `B02` [memory] **PASS** (48.7137s) 
- `B03` [memory] **PASS** (43.6072s) 
- `B04` [memory] **PASS** (146.4819s) 
- `B05` [memory] **PASS** (50.1728s) 
- `C01` [tools] **FAIL** (62.4289s) 
- `C02` [tools] **FAIL** (59.3053s) 
- `C03` [tools] **FAIL** (44.7185s) 
- `C04` [tools] **FAIL** (42.6406s) 
- `C05` [tools] **FAIL** (75.5248s) 
- `D01` [persistence] **PASS** (49.7669s) restart_after_setup
- `D02` [persistence] **PASS** (45.5561s) restart_after_setup
