from __future__ import annotations

from typing import Any, Dict, List


HEALTH_WEIGHTS = {
    "Memory": 0.15,
    "Planning": 0.15,
    "Trust": 0.15,
    "Adaptation": 0.10,
    "Learning": 0.10,
    "Evolution": 0.10,
}

HEALTH_BONUSES = {
    "trend_improving": 0.05,
    "capability_utilization_high": 0.05,
}

HEALTH_PENALTIES = {
    "active_regression": -0.10,
    "trend_declining": -0.05,
}

PREDICTION_CONFIDENCE = {
    "min_data_points": 3,
    "high_r_squared": 0.7,
    "medium_r_squared": 0.4,
}

CAPABILITY_IMPORTANCE = {
    "utilization_weight": 0.30,
    "contribution_weight": 0.30,
    "reliability_weight": 0.20,
    "freshness_weight": 0.20,
}

STRATEGY_CONFIDENCE = {
    "direct_evidence": 0.85,
    "indirect_evidence": 0.65,
    "inferred_evidence": 0.45,
}

FORECAST_DECAY = 0.05


def get_health_weights() -> Dict[str, Any]:
    return {
        "category_weights": dict(HEALTH_WEIGHTS),
        "bonuses": dict(HEALTH_BONUSES),
        "penalties": dict(HEALTH_PENALTIES),
        "prediction_confidence": dict(PREDICTION_CONFIDENCE),
        "capability_importance": dict(CAPABILITY_IMPORTANCE),
        "strategy_confidence": dict(STRATEGY_CONFIDENCE),
        "forecast_decay": FORECAST_DECAY,
        "version": "1.0.0",
    }


def apply_capability_lifecycle(
    raw_roi: List[Dict[str, Any]],
    trends: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    ranked = []
    for cap in raw_roi:
        utilization = cap.get("uses", 0) / max(cap.get("installed_day", 1), 1)
        contribution_total = sum(cap.get("contribution", {}).values())
        reliability = (
            cap.get("successful_uses", 0) / max(cap.get("uses", 1), 1)
            if cap.get("uses", 0) > 0
            else 0.0
        )
        rank_score = (
            CAPABILITY_IMPORTANCE["utilization_weight"] * min(utilization * 10, 100)
            + CAPABILITY_IMPORTANCE["contribution_weight"] * min(contribution_total * 5, 100)
            + CAPABILITY_IMPORTANCE["reliability_weight"] * reliability * 100
        )
        ranked.append({
            "cap_id": cap["cap_id"],
            "rank_score": round(rank_score, 1),
            "utilization_score": round(min(utilization * 10, 100), 1),
            "contribution_score": round(min(contribution_total * 5, 100), 1),
            "reliability_score": round(reliability * 100, 1),
            "current_recommendation": cap.get("recommendation", "KEEP"),
        })
    ranked.sort(key=lambda x: x["rank_score"], reverse=True)
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1
    return ranked
