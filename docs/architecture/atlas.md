# Atlas — Strategic Decision Layer for IdentityOS

## Why Atlas Exists

IdentityOS has three operational layers:

| Layer | Responsibility | Questions Answered |
|-------|---------------|-------------------|
| **Runtime** | Execute | Does it work? |
| **Prometheus** | Evolve | Can it acquire new capabilities? |
| **IdentityBench** | Measure & Explain | What happened? Why? |

These layers are reactive. They describe the present and explain the past.

**Atlas** is the **strategic layer**. It consumes IdentityBench's historical evidence and produces engineering decisions that answer:

- What will happen next?
- What should change?
- Which capabilities create the most value?
- Which capabilities should be archived?
- Which engineering strategy should be prioritized?
- What will be the expected impact of a change?

Atlas transforms IdentityOS from a system that **measures itself** into a system that **understands itself** and **directs its own evolution**.

## Non-Responsibilities

- Atlas does NOT run benchmarks.
- Atlas does NOT acquire capabilities.
- Atlas does NOT modify Prometheus's behavior.
- Atlas does NOT introduce ML, neural networks, or external services.
- Atlas does NOT modify IdentityBench's scoring.
- Atlas does NOT increase benchmark randomness or non-determinism.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Identity Runtime                       │
│  Executes capabilities, manages state, processes requests   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        Prometheus                           │
│  Detects capability gaps, searches registries, installs     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       IdentityBench                         │
│  Measures 7 categories: Memory, Planning, Trust,            │
│  Adaptation, Coordination, Learning, Evolution              │
│  Produces: scores, explanations, diffs, regressions,        │
│  recommendations, ROI, timeline, weekly reports             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                          Atlas                              │
│  Consumes IdentityBench history                             │
│  Produces:                                                  │
│    • Identity Health (synthesized metric)                   │
│    • Predictions (trend-based, per-category)                │
│    • Forecast (timeline, weekly projections)                │
│    • Evidence-Based Recommendations (correlation-driven)    │
│    • Capability Ranking (value-based lifecycle analysis)    │
│    • Strategies (goal-oriented action plans)                │
│    • Score Change Explanations (with root causes)           │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
IdentityBench Storage
├── run_history (List[Dict])
│   ├── timestamp
│   ├── overall_score
│   ├── category_scores
│   └── worlds
├── trend_data (List[Dict])
│   ├── timestamp
│   └── per-category values
└── capability_journal (per-capability JSON)
    ├── event_type
    ├── installation_success
    └── ...

        │
        ▼

Atlas Computation Pipeline:

1. trend_data ──► Prediction Engine ──► per-category predictions
                                              │
                     ┌────────────────────────┘
                     ▼
2. category_scores + predictions + regressions + rankings
            ──► Health Engine ──► Identity Health score

3. category_scores + predictions ──► Forecast Engine ──► Weekly forecast

4. capability_history + run_history ──► Impact Analyzer ──► Capability impacts

5. current_scores + impacts + predictions + regressions
            ──► Decision Engine ──► Evidence-based recommendations

6. health + predictions + recommendations + rankings
            ──► Strategy Engine ──► Evolution strategies

7. category + run_history + capability_history + diff
            ──► Score Change Explainer ──► Full explanation
```

## Module Reference

### `identitybench/atlas/health.py`

**`compute_identity_health(category_scores, regressions=None, predictions=None, capability_rankings=None)`**

Computes a single synthesized metric (0–100) derived from:
- Memory (15%)
- Planning (15%)
- Trust (15%)
- Adaptation (10%)
- Learning (10%)
- Evolution (10%)
- Regression penalty (up to -10%)
- Trend bonus/penalty (±5%)
- Capability utilization bonus (+5%)

Returns:
- `health`: float (0–100)
- `confidence`: float (0–1)
- `reasons`: list of human-readable explanation strings
- `contributions`: per-category contribution breakdown

### `identitybench/atlas/prediction.py`

**`predict_category_trend(category, historical_values, steps_ahead=5)`**

Uses linear least-squares regression on historical values. Produces:
- `predicted_value`: projected score after steps_ahead runs
- `slope`: pts per run
- `r_squared`: goodness of fit
- `confidence`: derived from data quality, fit, and trend strength
- `trend_direction`: "improving" / "declining" / "stable"
- `recommended_action`: context-relevant suggestion

**`predict_all_categories(trends, steps_ahead=5)`**

Runs `predict_category_trend` for all 6 primary categories.

### `identitybench/atlas/forecast.py`

**`build_forecast(category_scores, predictions, weeks=8)`**

Projects health and per-category scores forward N weeks using prediction slopes with decay.

**`format_forecast(forecast, detail_categories=None)`**

Renders ASCII table showing week-by-week projected health and scores.

### `identitybench/atlas/decision_engine.py`

**`analyze_capability_impact(capability_history, run_history)`**

For each successful installation, compares category scores before and after installation to measure impact.

**`generate_evidence_recommendations(current_scores, capability_impacts, predictions, regressions=None)`**

Produces typed recommendations (IMPROVE / INVESTIGATE) based on:
- Weak categories (score < 60)
- Historical capability impacts
- Predicted declines
- Active regressions

Confidence reflects strength of evidence.

### `identitybench/atlas/capability_lifecycle.py`

**`compute_capability_ranking(roi_data, run_history, capability_history=None)`**

Ranks capabilities by combined score of:
- Utilization (30%)
- Contribution to benchmark scores (30%)
- Reliability/success rate (20%)
- Freshness/days active (20%)

**`explain_score_change(category, previous_score, current_score, diff=None, run_history=None, capability_history=None)`**

Produces full explanation of any score change with root causes, evidence, and confidence.

### `identitybench/atlas/strategy.py`

**`generate_strategies(health, predictions, recommendations, capability_rankings=None)`**

Groups recommendations into goal-oriented strategies. Each strategy contains:
- Goal (e.g., "Improve Research score")
- Actions (e.g., "Acquire web search capability")
- Expected gain (points)
- Confidence (0–1)
- Supporting evidence

### `identitybench/atlas/weighting.py`

**`get_health_weights()`**

Returns all weights, bonuses, penalties, and configuration values used by Atlas computations. No magic numbers.

**`apply_capability_lifecycle(raw_roi, trends)`**

Enriches raw ROI data with ranked scores.

### `identitybench/atlas/interfaces.py`

Extension point interfaces for future versions:

| Interface | Methods | Future Use |
|-----------|---------|------------|
| `PredictionModel` | `predict()`, `supports_bayesian()`, `supports_ml()` | ML prediction, Bayesian confidence |
| `ConfidenceEstimator` | `estimate()`, `supports_bayesian()` | Bayesian confidence estimation |
| `StrategyOptimizer` | `optimize()`, `supports_reinforcement_learning()` | RL-based strategy optimization |
| `HealthAugmenter` | `augment()`, `supports_organization_dashboards()`, `supports_multi_identity()` | Organization dashboards, multi-identity comparison |

## CLI Commands

| Command | Description |
|---------|-------------|
| `identitybench forecast <id> --weeks 8` | Generate forecast timeline |
| `identitybench atlas <id> -o report.txt` | Full strategic analysis (health + predictions + recs + ranking + strategies) |

## Decision Lifecycle

```
1. IdentityBench produces run data
2. Atlas Prediction Engine processes trend data
3. Atlas Health Engine computes identity health
4. Atlas Decision Engine generates evidence-based recommendations
5. Atlas Strategy Engine produces action plans
6. Prometheus (optionally) consumes strategies for acquisition planning
7. Next benchmark run validates effectiveness
8. Cycle repeats
```

## Prediction Lifecycle

```
1. Collect N historical data points per category
2. Compute linear regression → slope, intercept, R²
3. Project value at N + steps_ahead
4. Estimate confidence from:
   - Data quality (min 3 points needed)
   - Fit quality (R²)
   - Trend strength
5. Determine direction (improving/declining/stable)
6. Generate recommended action
7. Clamp projected value to [0, 100]
```

## Health Computation

```
Health = Σ(category_score × weight)
        - regression_penalty
        + trend_bonus
        + capability_bonus

Weights:
  Memory:       0.15
  Planning:     0.15
  Trust:        0.15
  Adaptation:   0.10
  Learning:     0.10
  Evolution:    0.10
  (Total:       0.75 — remaining 0.25 reserved for future categories)

Penalties:
  Active regression (CRITICAL):  -8% of base per regression
  Active regression (WARNING):   -4% of base per regression
  Trend majority declining:      -5% of base

Bonuses:
  Trend majority improving:      +5% of base
  Capability utilization >80%:   +5% of base

Confidence:
  Base: 50% + category completeness × 30%
  Adjusted: -2% per active regression
  Adjusted: +20% × average prediction confidence
```

## Strategy Generation

Strategies target the weakest contributing categories. For each weak category:

1. Look up template actions from `_STRATEGY_TEMPLATES`
2. Determine expected gain from trend direction
3. Calculate confidence from evidence quality
4. Include capability ranking data if available
5. Sort by confidence descending

## Future Extension Points

The following are explicitly NOT implemented but are designed for via interfaces:

- **ML-based prediction**: Replace `_linear_regression` with `PredictionModel` implementation
- **Bayesian confidence**: Replace heuristic confidence with `ConfidenceEstimator` implementation
- **Reinforcement learning**: Replace static strategy templates with `StrategyOptimizer` implementation
- **Organization dashboards**: Extend `HealthAugmenter` for multi-identity aggregation
- **Multi-identity comparison**: `HealthAugmenter.supports_multi_identity()`
- **Capability market analytics**: Extend `compute_capability_ranking` with market data
- **Registry ecosystem analysis**: Extend strategy engine with registry awareness

## Testing

- **73 tests** in `tests/test_atlas.py`
- All tests are deterministic
- No external dependencies
- Isolation: Atlas never imports IdentityBench internals
- Coverage: Health, Prediction, Forecast, Strategy, Decision Engine, Capability Lifecycle, Weighting, Interfaces, Integration

## Separation Validation

- `identitybench/atlas/` is a standalone package
- Atlas only imports `identitybench.atlas.*` internally
- IdentityBench has no reference to Atlas in its package code
- The CLI imports Atlas (as it does all other modules), preserving separation
- Atlas consumes benchmark history as plain dicts — no runtime types
