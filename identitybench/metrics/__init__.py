from __future__ import annotations

from typing import Any, Dict, List

from .memory import MemoryMetrics
from .planning import PlanningMetrics
from .trust import TrustMetrics
from .adaptation import AdaptationMetrics
from .coordination import CoordinationMetrics
from .learning import LearningMetrics
from .evolution import EvolutionMetrics


def compute_all_metrics(transcript: List[dict], world_name: str = "") -> Dict[str, float]:
    classes = [MemoryMetrics, PlanningMetrics, TrustMetrics, AdaptationMetrics,
               CoordinationMetrics, LearningMetrics]
    if "evolution" in world_name.lower():
        classes.append(EvolutionMetrics)
    scores = {}
    for cls in classes:
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
        "Evolution": ["gap_detection", "search_quality", "install_success", "retry_success",
                       "adaptation_speed", "capability_reuse", "unnecessary_installs_prevented",
                       "performance_improvement", "evolution_score"],
    }
    cat_scores = {}
    for cat, keys in categories.items():
        vals = [scores.get(k, 0) for k in keys if scores.get(k) is not None]
        cat_scores[cat] = round(sum(vals) / len(vals), 1) if vals else 0.0
    learning_score = scores.get("learning_score", 0)
    cat_scores["Learning"] = learning_score
    return cat_scores


def compute_category_explanations(
    transcript: List[dict],
    world_name: str = "",
) -> Dict[str, Dict[str, list]]:
    classes = [MemoryMetrics, PlanningMetrics, TrustMetrics, AdaptationMetrics,
               CoordinationMetrics, LearningMetrics]
    if "evolution" in world_name.lower():
        classes.append(EvolutionMetrics)
    explanations: Dict[str, Dict[str, list]] = {}
    for cls in classes:
        try:
            m = cls(transcript, world_name)
            cat_name = cls.__name__.replace("Metrics", "")
            explanations[cat_name] = m.explain()
        except Exception:
            pass
    return explanations
