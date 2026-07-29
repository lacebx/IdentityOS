from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from identitybench.atlas.weighting import HEALTH_WEIGHTS, HEALTH_BONUSES, HEALTH_PENALTIES


def compute_identity_health(
    category_scores: Dict[str, float],
    regressions: Optional[List[Dict[str, Any]]] = None,
    predictions: Optional[List[Dict[str, Any]]] = None,
    capability_rankings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    base_score = 0.0
    contributions: Dict[str, float] = {}
    reasons: List[str] = []
    total_weight = 0.0

    for cat, weight in HEALTH_WEIGHTS.items():
        score = category_scores.get(cat, 0.0)
        contribution = score * weight
        base_score += contribution
        total_weight += weight
        contributions[cat] = round(contribution, 1)
        if score >= 80:
            reasons.append(f"{cat}: {score:.0f} (strong)")
        elif score >= 60:
            reasons.append(f"{cat}: {score:.0f} (adequate)")
        else:
            reasons.append(f"{cat}: {score:.0f} (needs improvement)")

    if total_weight > 0:
        base_score = base_score / total_weight
        for cat in contributions:
            contributions[cat] = round(contributions[cat] / total_weight, 1)

    penalty = 0.0
    regression_count = 0
    if regressions:
        for r in regressions:
            severity = r.get("severity", "INFO")
            if severity == "CRITICAL":
                penalty += 0.08
                regression_count += 1
            elif severity == "WARNING":
                penalty += 0.04
                regression_count += 1
    if regression_count > 0:
        applied = min(penalty, abs(HEALTH_PENALTIES["active_regression"]))
        base_score -= base_score * applied
        reasons.append(
            f"Regression penalty: -{applied:.0%} ({regression_count} active)"
        )

    trend_bonus = 0.0
    if predictions:
        improving = sum(
            1 for p in predictions if p.get("trend_direction") == "improving"
        )
        declining = sum(
            1 for p in predictions if p.get("trend_direction") == "declining"
        )
        total = len(predictions)
        if total > 0:
            net = (improving - declining) / total
            if net > 0.3:
                trend_bonus = HEALTH_BONUSES["trend_improving"]
                reasons.append("Trend bonus: +5% (majority improving)")
            elif net < -0.3:
                trend_bonus = HEALTH_PENALTIES["trend_declining"]
                reasons.append("Trend penalty: -5% (majority declining)")

    base_score += base_score * trend_bonus

    cap_bonus = 0.0
    if capability_rankings and len(capability_rankings) > 0:
        high_ranked = sum(1 for c in capability_rankings if c.get("rank_score", 0) > 50)
        total_caps = len(capability_rankings)
        if total_caps > 0 and high_ranked / total_caps > 0.8:
            cap_bonus = HEALTH_BONUSES["capability_utilization_high"]
            reasons.append("Capability bonus: +5% (high utilization)")

    base_score += base_score * cap_bonus

    health = round(max(0.0, min(base_score, 100.0)), 1)

    confidence = _compute_health_confidence(category_scores, regressions, predictions)
    return {
        "health": health,
        "confidence": confidence,
        "reasons": reasons,
        "contributions": contributions,
        "regression_count": regression_count,
        "trend_bonus": trend_bonus,
        "capability_bonus": cap_bonus,
    }


def _compute_health_confidence(
    category_scores: Dict[str, float],
    regressions: Optional[List[Dict[str, Any]]] = None,
    predictions: Optional[List[Dict[str, Any]]] = None,
) -> float:
    filled = sum(1 for v in category_scores.values() if v is not None and v > 0)
    total = len(category_scores)
    completeness = filled / total if total > 0 else 0.0
    base = 0.5 + completeness * 0.3
    if regressions and len(regressions) > 0:
        base -= 0.02 * len(regressions)
    if predictions:
        avg_confidence = sum(
            p.get("confidence", 0.0) for p in predictions
        ) / max(len(predictions), 1)
        base += avg_confidence * 0.2
    return round(max(0.1, min(base, 0.95)), 2)


def format_health(health_result: Dict[str, Any]) -> str:
    lines = [
        f"  Identity Health: {health_result['health']:.1f}/100 "
        f"(confidence: {health_result['confidence']:.0%})",
        "",
        "  Contributions:",
    ]
    for cat, val in sorted(health_result["contributions"].items()):
        weight = HEALTH_WEIGHTS.get(cat, 0.0)
        lines.append(f"    {cat:15s} {val:5.1f} pts  (weight: {weight:.0%})")
    lines.append("")
    lines.append("  Reasons:")
    for r in health_result["reasons"]:
        lines.append(f"    • {r}")
    return "\n".join(lines)
