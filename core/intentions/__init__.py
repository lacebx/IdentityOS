"""
core/intentions/__init__.py - Intention Engine

Intentions are short-term commitments formed during conversation.
They are NOT goals — they are steps toward goals or standalone promises.
Intentions auto-expire and can be promoted to goals.
"""

from .engine import (
    Intention,
    IntentionEngine,
    IntentionPriority,
    IntentionStatus,
    PromotionReason,
)

__all__ = [
    "Intention",
    "IntentionEngine",
    "IntentionPriority",
    "IntentionStatus",
    "PromotionReason",
]
