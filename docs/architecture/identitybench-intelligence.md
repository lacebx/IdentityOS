# IdentityBench Intelligence — Benchmark Analytics & Evolution Observability

**Architecture Document — Phase II**

---

## Purpose

IdentityBench started as a benchmark runner that answered "What happened?" This phase
transforms it into an engineering observability system that answers:

- Why did the score change?
- Which capabilities actually helped?
- What should the identity improve next?
- Is Prometheus making good decisions?

Every score now has evidence. Every improvement has a cause. Every regression has an
explanation. Nothing is a magic number.

---

## Architecture

```
identitybench/
├── engine.py                  — Benchmark runner (updated: captures analytics)
├── reporting.py               — Report generation (updated: explanations + diffs)
├── cli.py                     — CLI (updated: weekly, roi, timeline, prometheus commands)
├── storage.py                 — Run persistence (unchanged)
│
├── metrics/                   — Metric computation (each class now has explain())
│   ├── memory.py
│   ├── planning.py
│   ├── trust.py
│   ├── adaptation.py
│   ├── coordination.py
│   ├── learning.py
│   └── evolution.py
│
├── analytics/                 — NEW: Analysis layer
│   ├── diff.py                — Benchmark diff engine
│   ├── regression.py          — Regression signal detection
│   ├── root_cause.py          — Root cause analysis
│   ├── recommendations.py     — Recommendation engine
│   ├── roi.py                 — Capability ROI calculator
│   └── timeline.py            — Evolution timeline builder
│
├── journal/                   — NEW: Persistent journals
│   ├── capability_journal.py  — Per-capability lifecycle record
│   └── evolution_history.py   — Identity evolution + Prometheus health
│
├── reports/                   — NEW: Structured reports
│   └── weekly.py              — Weekly engineering report
│
└── visualization/             — NEW: ASCII visualization
    ├── timeline.py            — ASCII timeline renderer
    └── trends.py              — ASCII trend chart renderer
```

---

## Component Design

### Score Explanation Engine

Every metric class (`MemoryMetrics`, `PlanningMetrics`, etc.) now implements `explain()`.
This method returns:

```python
{
    "reasons": ["correctly recalled 4 facts", "hallucinated 1 fact"],
    "confidence": 0.85,
    "evidence_count": 12
}
```

This is rendered in reports as:

```
    Planning: 61.3 (+8.4)
      ✓ completed 4 scheduled tasks
      ✓ revisited 3 unfinished tasks
      ✗ forgot one deadline
      Confidence: 0.92
```

### Benchmark Diff Engine

`compute_benchmark_diff()` takes two run data dicts and produces:

```python
{
    "overall": {"previous": 72.0, "current": 78.0, "change": 6.0},
    "categories": [
        {"category": "Memory", "previous": 65, "current": 81, "change": 16,
         "verdict": "IMPROVED", "reasons": [...]}
    ],
    "worlds": [...]
}
```

### Root Cause Analysis

`analyze_root_causes()` links score changes to capability installations:

```
Planning improved
  because
  Installed Scheduler
  ↓
  scheduler reused 8 times
  ↓
  benchmark planning score +12
```

It uses a `_CAPABILITY_CATEGORY_MAP` to link known capabilities to the categories
they influence (e.g., `github` → Research, Planning).

### Capability ROI

`calculate_capability_roi()` produces per-capability lifecycles:

```python
{
    "cap_id": "github",
    "installed_day": 5,
    "uses": 48,
    "successful_uses": 47,
    "failures": 1,
    "contribution": {"Planning": 4.0, "Research": 11.0, "Trust": 2.0},
    "recommendation": "KEEP"
}
```

### Capability Journal

`CapabilityJournal` persists a JSON file per capability per identity at
`.identitybench/journals/<identity>/<cap_id>.json`. Each entry records:

- event_type (installation, SUCCEEDED, FAILED, ROLLED_BACK, validation_failure, etc.)
- timestamp
- details (trust_score, performance_gain, duration_ms, etc.)

Maximum 500 entries per capability.

### Regression Detection

`detect_regressions()` scans trend data for consecutive decreases exceeding a
threshold (default 3 consecutive drops of ≥2 pts each). Produces:

```python
{
    "metric": "Research",
    "consecutive_decreases": 4,
    "current_value": 37,
    "likely_causes": ["GitHub rate limits", "web search failures"],
    "severity": "WARNING"
}
```

### Prometheus Health

`EvolutionHistory.compute_prometheus_health()` aggregates evolution data into a
health score:

- gap_detection_accuracy
- search_quality
- install_success_rate
- validation_success
- retry_success
- capability_longevity
- overall_health (aggregate)

### Weekly Engineering Report

`generate_weekly_report()` combines all analytics into a single report:

```yaml
Identity: gabe
Runs: 18
Overall: 72 (+6)
Largest Improvement: Planning (+14)
Largest Regression: Trust (-2)
New Capabilities: GitHub, Filesystem, Weather
Unused Capabilities: Filesystem
Benchmark Recommendation: Archive filesystem
Prometheus Recommendation: Improve capability ranking
Confidence: 95%
```

### Learning vs Evolution

`EvolutionHistory.compute_learning_vs_evolution()` compares fact counts against
benchmark improvement to determine learning effectiveness:

| Facts Learned | Benchmark Improvement | Effectiveness |
|---------------|---------------------|---------------|
| 83 | 2% | Low |
| 21 | 19% | Excellent |

### Timeline Visualization

`build_evolution_timeline()` merges benchmark runs with capability events into a
chronological sequence rendered as ASCII:

```
  Day 1    ■ Benchmark #1          ████████░░ 72
  Day 1    + Installed GitHub
  Day 2    ↑ Planning improved by 12 pts (43 → 55)
  Day 4    ● Installed Scheduler
  Day 5    ■ Benchmark #2          █████████░ 84
  Day 5    ╳ Filesystem install rolled back
  Day 6    ↑ Memory declined by 8 pts (90 → 82)
```

---

## Data Flow

```
Benchmark Run
    │
    ├──► metrics/ → scores + explanations
    │
    ├──► storage.py → persisted to .identitybench/runs/
    │
    ├──► analytics/diff.py → compare vs previous run
    │
    ├──► analytics/regression.py → scan trends for regressions
    │
    ├──► analytics/root_cause.py → link changes to capabilities
    │
    ├──► analytics/recommendations.py → suggest next steps
    │
    ├──► analytics/roi.py → capability lifecycle analysis
    │
    ├──► analytics/timeline.py → chronological evolution log
    │
    ├──► journal/ → update capability journals + evolution history
    │
    └──► reports/weekly.py → structured engineering report
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `identitybench run <id>` | Run benchmarks (unchanged) |
| `identitybench report <id>` | Generate report with explanations + diffs + recommendations |
| `identitybench weekly <id>` | Generate weekly engineering report |
| `identitybench roi <id>` | Show capability ROI analysis |
| `identitybench timeline <id>` | Show evolution timeline |
| `identitybench prometheus <id>` | Show Prometheus health evaluation |
| `identitybench regressions <id>` | Detect regression signals |
| `identitybench history <id>` | Show run history (unchanged) |
| `identitybench compare` | Compare identities (unchanged) |

---

## Extension Points

| Point | Mechanism | Example |
|-------|-----------|---------|
| Add new metric | Create class in `metrics/` with `compute()` + `explain()` | `SecurityMetrics` |
| Add new world | Create class in `worlds/` extending `BenchmarkWorld` | `SecurityWorld` |
| Replace diff logic | Swap `compute_benchmark_diff()` | Custom diff algorithm |
| Replace regression detection | Swap `detect_regressions()` | ML-based detection |
| Replace recommendation engine | Swap `generate_recommendations()` | LLM-powered recs |
| Add new report type | Create module in `reports/` | `monthly.py` |
| Add new visualization | Create module in `visualization/` | HTML timeline |
| Custom capability→category map | Modify `_CAPABILITY_CATEGORY_MAP` in `root_cause.py` | Add new capabilities |

---

## Testing Philosophy

All tests must be deterministic. Analytics modules use pure functions with
no side effects (data in → data out). The journal modules read/write JSON
files and should use temporary directories in tests.

---

## Future Roadmap

### Short-term
- **Trend visualization**: ASCII sparklines for each category
- **Capability cost tracking**: Track latency/cost impact of each capability
- **Anomaly detection**: Statistical outlier detection in score distributions

### Medium-term
- **ML-based recommendations**: Learn from cross-identity patterns
- **Natural language reports**: LLM-generated narrative summaries
- **Export to external monitoring**: Prometheus/Grafana integration

### Long-term
- **Automated capability lifecycle**: IdentityBench recommends → Prometheus acts
- **Cross-identity analytics**: Compare evolution across all identities
- **Predictive scoring**: Forecast future scores based on acquisition trajectory
