"""
core/confidence - Generalized Confidence computation for all knowledge objects.

Provides a deterministic, evidence-chain-based confidence scorer that any
knowledge object (facts, goals, intentions, memories) can use.
"""

from .scorer import ConfidenceScorer

__all__ = ["ConfidenceScorer"]
