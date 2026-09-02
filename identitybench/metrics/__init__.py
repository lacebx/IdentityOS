from __future__ import annotations

from typing import Any, Dict, List

from .memory import MemoryMetrics
from .planning import PlanningMetrics
from .trust import TrustMetrics
from .adaptation import AdaptationMetrics
from .coordination import CoordinationMetrics
from .learning import LearningMetrics
from .evolution import EvolutionMetrics


METRIC_CHECK_TYPES = {
    "recall_accuracy": {"recall_check"},
    "false_memories": {"fabrication_check"},
    "forgotten_tasks": {"task_recall"},
    "completion_rate": {"task_assignment", "completion_check"},
    "deadline_accuracy": {"deadline_check"},
    "reprioritization_quality": {"reprioritization_check"},
    "truthfulness_rate": {"verification_check", "truth_check"},
    "hallucination_rate": {"verification_check", "truth_check"},
    "verification_rate": {"verification_check"},
    "stale_knowledge_detection": {"stale_knowledge_check"},
    "confidence_calibration": {"confidence_check"},
    "updated_beliefs": {"belief_update_check"},
    "corrected_assumptions": {"correction_check"},
    "proactive_verification": {"proactive_check"},
    "memory_leakage": {"memory_leakage_check"},
    "responsibility_leakage": {"responsibility_check"},
    "coordination_efficiency": {"handoff_check"},
    "pattern_recognition": {"pattern_check"},
    "preference_discovery": {"preference_check"},
    "self_correction": {"self_correction_check"},
    "gap_detection": {"gap_check"},
    "search_quality": {"search_check"},
    "install_success": {"install_check"},
    "retry_success": {"retry_check"},
    "adaptation_speed": {"evolution_entry"},
    "capability_reuse": {"reuse_check"},
    "unnecessary_installs_prevented": {"duplicate_check"},
    "performance_improvement": {"improvement_check"},
}


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
    observed_types = {entry.get("type") for entry in transcript}
    applicable = {
        metric: score
        for metric, score in scores.items()
        if metric in METRIC_CHECK_TYPES
        and observed_types.intersection(METRIC_CHECK_TYPES[metric])
    }
    if any(metric in applicable for metric in (
        "pattern_recognition", "preference_discovery", "self_correction",
    )):
        values = [
            applicable[metric]
            for metric in ("pattern_recognition", "preference_discovery", "self_correction")
            if metric in applicable
        ]
        applicable["learning_score"] = round(sum(values) / len(values), 1)
    if any(metric in applicable for metric in (
        "gap_detection", "search_quality", "install_success", "retry_success",
        "adaptation_speed", "capability_reuse", "unnecessary_installs_prevented",
        "performance_improvement",
    )):
        values = [
            applicable[metric]
            for metric in (
                "gap_detection", "search_quality", "install_success", "retry_success",
                "adaptation_speed", "capability_reuse", "unnecessary_installs_prevented",
                "performance_improvement",
            )
            if metric in applicable
        ]
        applicable["evolution_score"] = round(sum(values) / len(values), 1)
    return applicable


def compute_category_scores(scores: Dict[str, float]) -> Dict[str, float]:
    categories = {
        "Memory": ["recall_accuracy", "false_memories", "forgotten_tasks"],
        "Planning": ["completion_rate", "deadline_accuracy", "reprioritization_quality"],
        "Trust": ["truthfulness_rate", "verification_rate", "stale_knowledge_detection", "confidence_calibration"],
        "Adaptation": ["updated_beliefs", "corrected_assumptions", "proactive_verification"],
        "Coordination": ["memory_leakage", "responsibility_leakage", "coordination_efficiency"],
        "Evolution": ["gap_detection", "search_quality", "install_success", "retry_success",
                       "adaptation_speed", "capability_reuse", "unnecessary_installs_prevented",
                       "performance_improvement"],
        "Learning": ["pattern_recognition", "preference_discovery", "self_correction"],
    }
    cat_scores = {}
    for cat, keys in categories.items():
        vals = [scores[key] for key in keys if key in scores]
        if vals:
            cat_scores[cat] = round(sum(vals) / len(vals), 1)
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
            explanation = m.explain()
            if explanation.get("evidence_count", 0):
                explanations[cat_name] = explanation
        except Exception:
            pass
    return explanations
