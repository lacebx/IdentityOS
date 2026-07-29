from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from identitybench.atlas.weighting import CAPABILITY_IMPORTANCE


def compute_capability_ranking(
    roi_data: List[Dict[str, Any]],
    run_history: List[Dict[str, Any]],
    capability_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    ranked = []
    for cap in roi_data:
        cap_id = cap.get("cap_id", "unknown")
        uses = cap.get("uses", 0)
        successful = cap.get("successful_uses", 0)
        failures = cap.get("failures", 0)
        installed_day = cap.get("installed_day")
        contribution = cap.get("contribution", {})

        if uses > 0:
            success_rate = successful / uses
        else:
            success_rate = 0.0

        days_active = 0
        if installed_day is not None and run_history:
            last_run = run_history[-1].get("tick_offset", 0) if isinstance(run_history[-1], dict) else 0
            days_active = max(1, last_run - installed_day)
        else:
            days_active = 1

        utilization = uses / max(days_active, 1)
        total_contribution = sum(contribution.values())
        combined = (
            CAPABILITY_IMPORTANCE["utilization_weight"] * min(utilization * 20, 100)
            + CAPABILITY_IMPORTANCE["contribution_weight"] * min(total_contribution * 10, 100)
            + CAPABILITY_IMPORTANCE["reliability_weight"] * success_rate * 100
            + CAPABILITY_IMPORTANCE["freshness_weight"]
            * (100 if installed_day is not None else 0)
        )
        roi_label = _roi_label(combined)
        ranked.append({
            "cap_id": cap_id,
            "uses": uses,
            "success_rate": round(success_rate * 100, 1),
            "failures": failures,
            "avg_latency_ms": cap.get("avg_latency_ms", 0),
            "contribution": contribution,
            "total_contribution": round(total_contribution, 1),
            "rank_score": round(combined, 1),
            "roi_label": roi_label,
            "recommendation": _ranking_recommendation(roi_label, success_rate),
            "reason": _ranking_reason(roi_label, uses, success_rate, total_contribution),
        })
    ranked.sort(key=lambda x: x["rank_score"], reverse=True)
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1
    return ranked


def _roi_label(score: float) -> str:
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Moderate"
    else:
        return "Low"


def _ranking_recommendation(roi_label: str, success_rate: float) -> str:
    if roi_label == "Excellent":
        return "Keep"
    elif roi_label == "Good":
        return "Keep"
    elif roi_label == "Moderate":
        return "Monitor"
    else:
        return "Consider Archiving"


def _ranking_reason(
    roi_label: str,
    uses: int,
    success_rate: float,
    total_contribution: float,
) -> str:
    parts = []
    if roi_label == "Excellent":
        parts.append("High utilization")
    elif roi_label == "Low":
        parts.append("Low utilization")
    if uses > 0:
        if success_rate >= 0.95:
            parts.append("Very reliable")
        elif success_rate >= 0.8:
            parts.append("Reliable")
        else:
            parts.append(f"Failure rate: {(1-success_rate)*100:.0f}%")
    if total_contribution > 5:
        parts.append(f"Strong benchmark contribution (+{total_contribution:.0f})")
    elif total_contribution < 1:
        parts.append("Minimal benchmark contribution")
    return ", ".join(parts) if parts else "No data"


def format_capability_ranking(ranked: List[Dict[str, Any]]) -> str:
    if not ranked:
        return "  No capabilities to rank."
    lines = [
        "  Capability Ranking (by value):",
        "",
    ]
    for entry in ranked:
        lines.append(
            f"  #{entry['rank']} {entry['cap_id']:20s} "
            f"Score: {entry['rank_score']:5.1f}  "
            f"ROI: {entry['roi_label']:10s}  "
            f"Rec: {entry['recommendation']}"
        )
        lines.append(
            f"      Uses: {entry['uses']}  "
            f"Success: {entry['success_rate']:.0f}%  "
            f"Failures: {entry['failures']}"
        )
        lines.append(f"      {entry['reason']}")
        lines.append("")
    return "\n".join(lines)


def explain_score_change(
    category: str,
    previous_score: float,
    current_score: float,
    diff: Optional[Dict[str, Any]] = None,
    run_history: Optional[List[Dict[str, Any]]] = None,
    capability_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    delta = current_score - previous_score
    direction = "improved" if delta > 0 else ("declined" if delta < 0 else "stable")

    root_causes: List[str] = []
    evidence: List[str] = []

    evidence.append(f"Previous: {previous_score:.1f}")
    evidence.append(f"Current:  {current_score:.1f}")
    evidence.append(f"Delta:    {delta:+.1f}")

    if diff:
        for cat_entry in diff.get("categories", []):
            if cat_entry.get("category") == category:
                root_causes.extend(cat_entry.get("reasons", []))
                evidence.extend(cat_entry.get("reasons", []))

    if capability_history:
        relevant_events = []
        for entry in capability_history:
            cap_id = entry.get("cap_id", entry.get("chosen_capability", ""))
            event_type = entry.get("event_type", "")
            if cap_id and event_type in ("installation", "SUCCEEDED", "FAILED"):
                relevant_events.append(f"{cap_id} {event_type}")
        if relevant_events:
            root_causes.append(
                f"Capability events during period: {', '.join(relevant_events[:5])}"
            )

    if run_history:
        cat_trend = []
        for run in run_history[-10:]:
            scores = run.get("category_scores", {})
            if isinstance(scores, dict) and category in scores:
                cat_trend.append(scores[category])
        if len(cat_trend) >= 3:
            recent = cat_trend[-3:]
            if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
                root_causes.append(f"Consistent increase over last {len(recent)} runs")
            elif all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
                root_causes.append(f"Consistent decrease over last {len(recent)} runs")

    confidence = 0.5
    if len(root_causes) >= 2:
        confidence = 0.75
    elif root_causes:
        confidence = 0.6
    if abs(delta) >= 10:
        confidence = min(confidence + 0.1, 0.95)

    return {
        "category": category,
        "previous": round(previous_score, 1),
        "current": round(current_score, 1),
        "delta": round(delta, 1),
        "direction": direction,
        "root_causes": root_causes,
        "evidence": evidence,
        "confidence": round(confidence, 2),
    }
