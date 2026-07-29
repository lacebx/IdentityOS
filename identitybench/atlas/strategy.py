from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from identitybench.atlas.weighting import STRATEGY_CONFIDENCE

_STRATEGY_TEMPLATES = {
    "Improve Research": {
        "goal": "Improve Research score",
        "actions": [
            "Acquire web search capability",
            "Improve GitHub reliability",
            "Increase capability reuse",
        ],
        "target_categories": ["Research"],
    },
    "Improve Trust": {
        "goal": "Improve Trust score",
        "actions": [
            "Reduce low-confidence answers",
            "Increase verification frequency",
            "Archive unreliable capability",
        ],
        "target_categories": ["Trust"],
    },
    "Improve Memory": {
        "goal": "Improve Memory score",
        "actions": [
            "Compress episodic memories",
            "Prune stale context",
            "Increase fact verification",
        ],
        "target_categories": ["Memory"],
    },
    "Improve Planning": {
        "goal": "Improve Planning score",
        "actions": [
            "Acquire scheduler capability",
            "Improve deadline tracking",
            "Review task prioritization",
        ],
        "target_categories": ["Planning"],
    },
    "Improve Adaptation": {
        "goal": "Improve Adaptation score",
        "actions": [
            "Increase proactive verification",
            "Perform more belief updates",
            "Correct assumptions earlier",
        ],
        "target_categories": ["Adaptation"],
    },
    "Improve Learning": {
        "goal": "Improve Learning score",
        "actions": [
            "Increase pattern recognition exercises",
            "Expand preference discovery",
            "Increase self-correction frequency",
        ],
        "target_categories": ["Learning"],
    },
    "Improve Evolution": {
        "goal": "Improve Evolution score",
        "actions": [
            "Expand capability registry",
            "Increase acquisition attempts",
            "Improve search quality",
        ],
        "target_categories": ["Evolution"],
    },
}


def generate_strategies(
    health: Dict[str, Any],
    predictions: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
    capability_rankings: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    strategies: List[Dict[str, Any]] = []

    weak_cats = _find_weak_categories(health, predictions, recommendations)
    for cat_name, cat_info in weak_cats:
        template = _STRATEGY_TEMPLATES.get(f"Improve {cat_name}")
        if not template:
            continue
        actions = list(template["actions"])
        expected_gain = cat_info.get("expected_gain", 5.0)
        confidence = cat_info.get("confidence", STRATEGY_CONFIDENCE["inferred_evidence"])

        supporting_evidence = cat_info.get("evidence", [])
        if capability_rankings:
            top_caps = [c for c in capability_rankings if c.get("rank", 0) <= 3]
            if top_caps:
                top_ids = [c["cap_id"] for c in top_caps]
                actions.append(f"Leverage high-value capabilities: {', '.join(top_ids)}")
                supporting_evidence.append(
                    f"Top capabilities available: {', '.join(top_ids)}"
                )

        strategies.append({
            "name": f"Improve {cat_name}",
            "goal": template["goal"],
            "actions": actions,
            "expected_gain": round(expected_gain, 1),
            "confidence": round(confidence, 2),
            "supporting_evidence": supporting_evidence,
        })

    strategies.sort(key=lambda x: x["confidence"], reverse=True)
    return strategies


def _find_weak_categories(
    health: Dict[str, Any],
    predictions: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    weak: List[Tuple[str, Dict[str, Any]]] = []
    contributions = health.get("contributions", {})
    for cat, contrib in sorted(contributions.items(), key=lambda x: x[1]):
        if contrib < 10:
            prediction = next(
                (p for p in predictions if p.get("category") == cat),
                None,
            )
            rec = next(
                (r for r in recommendations if r.get("target") == cat),
                None,
            )
            evidence: List[str] = []
            expected_gain = 5.0
            confidence = STRATEGY_CONFIDENCE["inferred_evidence"]

            if prediction:
                direction = prediction.get("trend_direction", "stable")
                if direction == "declining":
                    expected_gain = 8.0
                    confidence = STRATEGY_CONFIDENCE["indirect_evidence"]
                    evidence.append(
                        f"{cat} is declining "
                        f"({prediction.get('slope', 0):+.1f} pts/run)"
                    )
                elif direction == "stable":
                    expected_gain = 5.0
                    confidence = STRATEGY_CONFIDENCE["inferred_evidence"]
                    evidence.append(f"{cat} is stable but below target")
                else:
                    expected_gain = 3.0
                    confidence = STRATEGY_CONFIDENCE["indirect_evidence"]
                    evidence.append(f"{cat} is improving but still below target")

            if rec:
                rec_evidence = rec.get("evidence", [])
                evidence.extend(rec_evidence[:2])
                if rec.get("confidence", 0) > confidence:
                    confidence = rec["confidence"]
                if rec.get("action") == "IMPROVE":
                    expected_gain = max(expected_gain, 10.0)

            weak.append((
                cat,
                {
                    "expected_gain": expected_gain,
                    "confidence": confidence,
                    "evidence": evidence,
                },
            ))
    return weak


def format_strategies(strategies: List[Dict[str, Any]]) -> str:
    if not strategies:
        return "  No strategies recommended at this time."
    lines = ["  Recommended Strategies:", ""]
    for s in strategies:
        lines.append(f"  Strategy: {s['name']}")
        lines.append(f"    Goal: {s['goal']}")
        lines.append(f"    Expected gain: {s['expected_gain']:+.1f} pts")
        lines.append(f"    Confidence: {s['confidence']:.0%}")
        lines.append("    Actions:")
        for action in s.get("actions", []):
            lines.append(f"      • {action}")
        if s.get("supporting_evidence"):
            lines.append("    Evidence:")
            for e in s["supporting_evidence"]:
                lines.append(f"      • {e}")
        lines.append("")
    return "\n".join(lines)
