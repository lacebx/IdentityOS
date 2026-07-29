from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from identitybench.atlas.weighting import STRATEGY_CONFIDENCE

_CATEGORY_CAPABILITY_MAP = {
    "github": ["Research", "Planning"],
    "weather": ["Research"],
    "calc": ["Planning", "Research"],
    "web_search": ["Research", "Trust"],
    "web": ["Research", "Trust"],
    "datetime": ["Planning"],
    "filesystem": ["Memory", "Research"],
    "text": ["Adaptation", "Research"],
    "system_info": ["Trust"],
    "scheduler": ["Planning"],
    "calendar": ["Planning"],
    "task_graph": ["Planning"],
    "project_management": ["Planning"],
}


def analyze_capability_impact(
    capability_history: List[Dict[str, Any]],
    run_history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    install_events = [
        e for e in capability_history
        if e.get("event_type") == "installation" and e.get("installation_success")
    ]
    for event in install_events:
        cap_id = event.get("cap_id", event.get("chosen_capability", "unknown"))
        install_day = event.get("tick_offset", event.get("installed_day", 0))

        affected_categories = _CATEGORY_CAPABILITY_MAP.get(cap_id, [])
        deltas: Dict[str, float] = {}
        pre_scores: Dict[str, float] = {}
        post_scores: Dict[str, float] = {}
        evidence: List[str] = []

        for cat in affected_categories:
            pre = _get_score_before_day(run_history, cat, install_day)
            post = _get_score_after_day(run_history, cat, install_day)
            if pre is not None and post is not None:
                pre_scores[cat] = pre
                post_scores[cat] = post
                deltas[cat] = round(post - pre, 1)
                arrow = "+" if deltas[cat] >= 0 else ""
                evidence.append(
                    f"{cat}: {pre:.0f} → {post:.0f} ({arrow}{deltas[cat]:.1f})"
                )

        if not deltas:
            continue

        avg_delta = sum(deltas.values()) / len(deltas)
        confidence = _impact_confidence(avg_delta, len(deltas), run_history)
        results.append({
            "capability": cap_id,
            "installed_day": install_day,
            "affected_categories": affected_categories,
            "deltas": deltas,
            "average_delta": round(avg_delta, 1),
            "confidence": confidence,
            "evidence": evidence,
        })
    results.sort(key=lambda x: abs(x["average_delta"]), reverse=True)
    return results


def _get_score_before_day(
    run_history: List[Dict[str, Any]],
    category: str,
    day: int,
) -> Optional[float]:
    before = [
        r for r in run_history
        if r.get("tick_offset", 9999) < day
    ]
    if not before:
        return None
    return before[-1].get("category_scores", {}).get(category)


def _get_score_after_day(
    run_history: List[Dict[str, Any]],
    category: str,
    day: int,
) -> Optional[float]:
    after = [
        r for r in run_history
        if r.get("tick_offset", -1) >= day
    ]
    if not after:
        return None
    return after[0].get("category_scores", {}).get(category)


def _impact_confidence(
    avg_delta: float,
    num_categories: int,
    run_history: List[Dict[str, Any]],
) -> float:
    base = STRATEGY_CONFIDENCE["indirect_evidence"]
    if abs(avg_delta) > 10 and num_categories >= 2:
        base = STRATEGY_CONFIDENCE["direct_evidence"]
    elif abs(avg_delta) < 2 or num_categories == 0:
        base = STRATEGY_CONFIDENCE["inferred_evidence"]
    if len(run_history) > 10:
        base = min(base + 0.1, 0.95)
    return round(base, 2)


def generate_evidence_recommendations(
    current_scores: Dict[str, float],
    capability_impacts: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
    regressions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []

    weak_categories = {
        cat: score for cat, score in current_scores.items()
        if score < 60
    }

    for cat, score in weak_categories.items():
        recommended_caps = [
            cap_id for cap_id, cats in _CATEGORY_CAPABILITY_MAP.items()
            if cat in cats
        ]
        evidence = [
            f"{cat} score is {score:.0f}/100 (below 60 threshold)",
        ]
        for impact in capability_impacts:
            for aff_cat, delta in impact["deltas"].items():
                if aff_cat == cat and delta > 0:
                    evidence.append(
                        f"{impact['capability']} installation associated with "
                        f"{cat} {delta:+.1f}"
                    )
        recommendations.append({
            "action": "IMPROVE",
            "target": cat,
            "current_score": score,
            "suggested_capabilities": recommended_caps[:3],
            "evidence": evidence[:5],
            "confidence": _rec_confidence(evidence, score),
        })

    if regressions:
        for r in regressions:
            metric = r.get("metric", "")
            recommendations.append({
                "action": "INVESTIGATE",
                "target": metric,
                "current_score": r.get("current_value", 0),
                "suggested_capabilities": [],
                "evidence": [
                    f"{metric}: {r.get('consecutive_decreases', 0)} consecutive decreases",
                    f"Severity: {r.get('severity', 'INFO')}",
                ],
                "confidence": 0.8 if r.get("severity") == "CRITICAL" else 0.6,
            })

    for pred in predictions:
        if pred.get("trend_direction") == "declining" and pred.get("confidence", 0) > 0.6:
            existing = any(
                r.get("target") == pred["category"] and r.get("action") == "INVESTIGATE"
                for r in recommendations
            )
            if not existing:
                recommendations.append({
                    "action": "INVESTIGATE",
                    "target": pred["category"],
                    "current_score": pred.get("current_value", 0),
                    "suggested_capabilities": [],
                    "evidence": [
                        f"Predicted decline from {pred['current_value']:.0f} "
                        f"to {pred['predicted_value']:.0f}",
                    ],
                    "confidence": pred.get("confidence", 0.5),
                })

    recommendations.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return recommendations


def _rec_confidence(evidence: List[str], score: float) -> float:
    base = STRATEGY_CONFIDENCE["inferred_evidence"]
    if score < 30:
        base = STRATEGY_CONFIDENCE["direct_evidence"]
    elif score < 50:
        base = STRATEGY_CONFIDENCE["indirect_evidence"]
    if len(evidence) > 2:
        base = min(base + 0.1, 0.95)
    return round(base, 2)


def format_evidence_recommendation(rec: Dict[str, Any]) -> str:
    lines = [
        f"  [{rec.get('action', '?')}] {rec.get('target', '?')} "
        f"(confidence: {rec.get('confidence', 0):.0%})"
    ]
    if "current_score" in rec:
        lines[0] += f"  [Score: {rec['current_score']:.0f}]"
    for e in rec.get("evidence", []):
        lines.append(f"    • {e}")
    if rec.get("suggested_capabilities"):
        lines.append(
            f"    Suggested: {', '.join(rec['suggested_capabilities'])}"
        )
    return "\n".join(lines)
