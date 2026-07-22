# ADR-004: Evidence-Based Confidence Over Statistical Models

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** Architecture Council
**Constitutional Basis:** Article XIII (Confidence)

---

## Context

The system needs to express certainty about its knowledge. Options include statistical models (Bayesian networks), machine learning confidence scoring, or deterministic evidence-chain computation.

## Decision

Use deterministic evidence-chain confidence computation. Confidence is computed from the number of corroborating evidence records and the number of unique values (contradictions). The formula is:

- Reinforcement: `min(1.0, 0.65 + 0.05 × n)` where n = number of agreeing records
- Contradiction threshold: `max(0.1, 0.7 - 0.15 × (u - 1))` where u = unique values
- Conflicting evidence: `min(reinforcement_score, contradiction_threshold)`

## Rationale

1. **Determinism** — Same evidence always produces same confidence. Essential for auditability.
2. **Simplicity** — No model training, no external dependencies, easy to reason about.
3. **Constitutional compliance** — Article XIII requires deterministic, auditable confidence.
4. **Transparency** — Any user can understand why confidence is at a given level.

## Consequences

- Positive: Fully auditable, deterministic, simple
- Positive: Zero external dependencies for confidence computation
- Negative: Cannot capture complex confidence patterns (e.g., source reliability weighting)
- Negative: Confidence plateaus at 1.0 after 7 corroborations, losing differentiation

## Compliance

- `core/user_profile.py` — `_compute_confidence()` in UserFact
- `core/identity_facts.py` — Evidence chain confidence computation
