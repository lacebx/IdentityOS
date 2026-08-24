# Run idos-20260819T215012Z

- mode: `idos`
- model: `smollm2:360m-instruct-q4_0`
- benchmark: `v0.1.0`
- updated_at: `2026-08-19T21:54:36.716251+00:00`
- tasks completed: `4`
- success: `1/4` (25%)
- hallucination: `0/4` (0%)
- avg latency: `66.0205s`

## Categories

| Category | Success | Hallucination | Avg latency |
|---|---|---|---|
| persistence | 1/4 (25%) | 0/4 (0%) | 66.0205s |

## Tasks

- `D01` [persistence] **FAIL** (41.3018s) restart_after_setup
- `D02` [persistence] **PASS** (42.9514s) restart_after_setup
- `D03` [persistence] **FAIL** (51.175s) restart_after_setup
- `D04` [persistence] **FAIL** (128.6539s) restart_after_setup
