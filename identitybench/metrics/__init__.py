from __future__ import annotations

from typing import Dict, List

from .memory import MemoryMetrics
from .planning import PlanningMetrics
from .trust import TrustMetrics
from .adaptation import AdaptationMetrics
from .coordination import CoordinationMetrics
from .learning import LearningMetrics


def compute_all_metrics(transcript: List[dict], world_name: str = "") -> Dict[str, float]:
    scores = {}
    for cls in [MemoryMetrics, PlanningMetrics, TrustMetrics, AdaptationMetrics, CoordinationMetrics, LearningMetrics]:
        try:
            m = cls(transcript, world_name)
            scores.update(m.compute())
        except Exception:
            pass
    return scores


def compute_category_scores(scores: Dict[str, float]) -> Dict[str, float]:
    categories = {
        "Memory": ["recall_accuracy", "false_memories", "forgotten_tasks"],
        "Planning": ["completion_rate", "deadline_accuracy", "reprioritization_quality"],
        "Trust": ["hallucination_rate", "verification_rate", "stale_knowledge_detection", "confidence_calibration"],
        "Adaptation": ["updated_beliefs", "corrected_assumptions", "proactive_verification"],
        "Coordination": ["memory_leakage", "responsibility_leakage", "coordination_efficiency"],
    }
    cat_scores = {}
    for cat, keys in categories.items():
        vals = [scores.get(k, 0) for k in keys if scores.get(k) is not None]
        cat_scores[cat] = round(sum(vals) / len(vals), 1) if vals else 0.0
    learning_score = scores.get("learning_score", 0)
    cat_scores["Learning"] = learning_score
    return cat_scores
