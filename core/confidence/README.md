# Confidence Scorer

**Path:** `core/confidence/`

## Overview

A deterministic, evidence-chain-based confidence computation used by all knowledge objects (facts, goals, intentions). Pure functions — no state, no side effects.

## Formula

- **Reinforcement:** `min(1.0, 0.65 + 0.05 × n)` for n corroborating records
- **Contradiction threshold:** `max(0.1, 0.7 - 0.15 × (u - 1))` where u = unique values
- **Final:** `min(reinforcement, contradiction_threshold)`

## Key Methods

- `compute(n_agreeing, n_unique_values)` — From raw counts
- `compute_from_values(values, current_value)` — From a list of observed values
- `compute_from_evidence_records(records)` — From evidence record objects
- `label(confidence)` — "high", "moderate", "low", "very_low"
- `description(confidence)` — Human-readable description

## Confidence Levels

| Range | Label | Expression |
|-------|-------|------------|
| 0.85–1.0 | high | Decisive, certain |
| 0.65–0.85 | moderate | Confident but open |
| 0.50–0.65 | low | Express uncertainty |
| 0.00–0.50 | very_low | Admit not knowing |

## Integration

Used by: `UserFact`, `Goal`, `Intention`, `EvidenceGraph`

Each knowledge object exposes `confidence` (computed) and `confidence_label` (cached or computed).
