"""
core/confidence/scorer.py - Deterministic evidence-chain confidence computation.

Formula (from Confidence Law):
  - Reinforcement:  min(1.0, 0.65 + 0.05 * n) for n corroborating records
  - Contradiction:  max(0.1, 0.7 - 0.15 * (unique_values - 1))
  - Final:          min(reinforcement, contradiction_threshold)

This is a pure function — no state, no side effects.
"""

from typing import Any, List


_CONFIDENCE_LABELS = [
    (0.85, "high"),
    (0.65, "moderate"),
    (0.50, "low"),
    (0.00, "very_low"),
]


class ConfidenceScorer:
    """Pure-function confidence computation from evidence chains."""

    @staticmethod
    def compute(
        n_agreeing: int,
        n_unique_values: int,
    ) -> float:
        """Compute confidence from raw counts.

        Args:
            n_agreeing: Number of evidence records that agree on the current value.
            n_unique_values: Number of distinct values observed across all evidence.
        """
        if n_agreeing < 0 or n_unique_values < 1:
            return 0.65

        reinforcement = min(1.0, 0.65 + 0.05 * n_agreeing)

        if n_unique_values > 1:
            penalty = max(0.1, 0.7 - 0.15 * (n_unique_values - 1))
            return min(reinforcement, penalty)

        return reinforcement

    @staticmethod
    def compute_from_values(values: List[Any], current_value: Any = None) -> float:
        """Compute confidence from a list of observed values.

        Args:
            values: All observed evidence values.
            current_value: The current/winning value. If None, uses the most
                          common value in the list, or the last value.
        """
        if not values:
            return 0.65

        str_values = [str(v) for v in values]
        unique = len(set(str_values))

        if current_value is None:
            from collections import Counter
            counter = Counter(str_values)
            current_str = counter.most_common(1)[0][0]
        else:
            current_str = str(current_value)

        n_agreeing = sum(1 for v in str_values if v == current_str)

        return ConfidenceScorer.compute(n_agreeing, unique)

    @staticmethod
    def compute_from_evidence_records(
        records: List[Any],
        value_attr: str = "value",
        current_value: Any = None,
    ) -> float:
        """Compute confidence from a list of evidence record objects.

        Args:
            records: List of objects with a *value_attr* attribute.
            value_attr: Attribute name for the evidence value on each record.
            current_value: The current/winning value.
        """
        values = [getattr(r, value_attr, str(r)) for r in records]
        return ConfidenceScorer.compute_from_values(values, current_value)

    @staticmethod
    def label(confidence: float) -> str:
        """Return a human-readable label for a confidence score."""
        for threshold, label in _CONFIDENCE_LABELS:
            if confidence >= threshold:
                return label
        return "very_low"

    @staticmethod
    def description(confidence: float) -> str:
        """Return a description string for a confidence score."""
        labels = {
            "high": "high confidence",
            "moderate": "moderate confidence",
            "low": "low confidence — may be uncertain",
            "very_low": "very low confidence — likely uncertain",
        }
        return labels.get(ConfidenceScorer.label(confidence), "unknown confidence")
