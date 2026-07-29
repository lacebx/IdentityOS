from __future__ import annotations

from typing import Any, Dict, List, Optional


def generate_recommendations(
    cat_scores: Dict[str, float],
    trends: Optional[List[Dict[str, Any]]] = None,
    regressions: Optional[List[Dict[str, Any]]] = None,
    capability_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []

    # Generate from weak categories
    for cat, score in sorted(cat_scores.items(), key=lambda x: x[1]):
        if score >= 70:
            continue
        rec = _recommend_for_category(cat, score)
        if rec:
            recommendations.append(rec)

    # Generate from regression signals
    if regressions:
        for sig in regressions:
            if sig.get("severity") in ("CRITICAL", "WARNING"):
                recommendations.append({
                    "action": "INVESTIGATE",
                    "target": sig.get("metric", "unknown"),
                    "evidence": [
                        f"Decreased for {sig.get('consecutive_decreases')} consecutive runs",
                        f"Current value: {sig.get('current_value')}",
                    ],
                    "estimated_impact": _estimate_impact(sig.get("severity", "INFO")),
                    "confidence": 0.85 if sig.get("severity") == "CRITICAL" else 0.7,
                })

    # Generate from unused capabilities
    if capability_history:
        unused = [c for c in capability_history if c.get("uses", 0) == 0 and c.get("event_type") == "installation"]
        for cap in unused:
            recommendations.append({
                "action": "ARCHIVE",
                "target": cap.get("cap_id", "unknown"),
                "evidence": [
                    f"Installed but never used",
                    f"Installed on day {cap.get('installed_day', '?')}",
                ],
                "estimated_impact": 0,
                "confidence": 0.6,
            })

    # Generate from trends if present
    if trends and len(trends) >= 2:
        sorted_trends = sorted(trends, key=lambda x: x.get("timestamp", ""))
        recent = sorted_trends[-1]
        prev = sorted_trends[-2]
        for cat in cat_scores:
            curr_val = recent.get(cat, 0) or 0
            prev_val = prev.get(cat, 0) or 0
            if curr_val < prev_val and curr_val < 70:
                existing = [r for r in recommendations if r.get("target") == cat]
                if not existing:
                    recommendations.append({
                        "action": "IMPROVE",
                        "target": cat,
                        "evidence": [
                            f"{cat} regressed from {prev_val} to {curr_val}",
                            f"Declined for at least 1 consecutive run",
                        ],
                        "estimated_impact": round((70 - curr_val) * 0.3, 1),
                        "confidence": 0.65,
                    })

    recs_by_action = {"IMPROVE": [], "ARCHIVE": [], "INVESTIGATE": [], "INSTALL": []}
    for r in recommendations:
        recs_by_action.setdefault(r.get("action", "IMPROVE"), []).append(r)

    result = []
    for action in ["IMPROVE", "INVESTIGATE", "ARCHIVE", "INSTALL"]:
        result.extend(recs_by_action.get(action, []))

    return result


def _recommend_for_category(cat: str, score: float) -> Optional[Dict[str, Any]]:
    cat_cap_map = {
        "Memory": {
            "action": "IMPROVE",
            "target": "Memory",
            "evidence": [f"Score {score} — recall or fact retention needs work"],
            "caps": ["filesystem"],
            "impact": round((70 - score) * 0.4, 1),
        },
        "Planning": {
            "action": "IMPROVE",
            "target": "Planning",
            "evidence": [f"Score {score} — task scheduling or deadline tracking needs work"],
            "caps": ["scheduler", "calendar", "task_graph", "project_management"],
            "impact": round((70 - score) * 0.4, 1),
        },
        "Trust": {
            "action": "IMPROVE",
            "target": "Trust",
            "evidence": [f"Score {score} — hallucination rate or verification needs work"],
            "caps": ["web", "system_info"],
            "impact": round((70 - score) * 0.3, 1),
        },
        "Adaptation": {
            "action": "IMPROVE",
            "target": "Adaptation",
            "evidence": [f"Score {score} — belief updating or correction handling needs work"],
            "caps": ["text"],
            "impact": round((70 - score) * 0.3, 1),
        },
        "Coordination": {
            "action": "IMPROVE",
            "target": "Coordination",
            "evidence": [f"Score {score} — memory leakage or handoff quality needs work"],
            "caps": [],
            "impact": round((70 - score) * 0.3, 1),
        },
        "Evolution": {
            "action": "IMPROVE",
            "target": "Evolution",
            "evidence": [f"Score {score} — gap detection or install reliability needs work"],
            "caps": [],
            "impact": round((70 - score) * 0.4, 1),
        },
    }
    entry = cat_cap_map.get(cat)
    if not entry:
        return None
    return {
        "action": entry["action"],
        "target": entry["target"],
        "evidence": entry["evidence"],
        "suggested_capabilities": entry["caps"],
        "estimated_impact": entry["impact"],
        "confidence": _confidence_from_score(score),
    }


def _confidence_from_score(score: float) -> float:
    if score < 30:
        return 0.95
    if score < 50:
        return 0.85
    if score < 70:
        return 0.7
    return 0.5


def _estimate_impact(severity: str) -> float:
    if severity == "CRITICAL":
        return 15.0
    if severity == "WARNING":
        return 8.0
    return 3.0


def format_recommendations(recs: List[Dict[str, Any]], top_n: int = 5) -> str:
    if not recs:
        return "  No recommendations at this time."

    lines: List[str] = []
    for rec in recs[:top_n]:
        action_tag = {
            "IMPROVE": "↑",
            "ARCHIVE": "↓",
            "INVESTIGATE": "!",
            "INSTALL": "+",
        }.get(rec.get("action", ""), "?")
        target = rec.get("target", "unknown")
        impact = rec.get("estimated_impact")
        conf = rec.get("confidence", 0)
        impact_str = f" (+{impact})" if impact else ""
        lines.append(f"  [{action_tag}] {target}{impact_str}  [confidence: {conf:.0%}]")
        for ev in rec.get("evidence", [])[:2]:
            lines.append(f"      Evidence: {ev}")
        caps = rec.get("suggested_capabilities", [])
        if caps:
            lines.append(f"      Suggested capabilities: {', '.join(caps)}")
    return "\n".join(lines)
