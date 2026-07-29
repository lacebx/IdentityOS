from __future__ import annotations

from typing import Any, Dict, List, Optional


def analyze_root_causes(
    diff: Dict[str, Any],
    prev_run: dict,
    curr_run: dict,
    capability_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    explanations: List[Dict[str, Any]] = []

    for cat_diff in diff.get("categories", []):
        if cat_diff["verdict"] == "STABLE":
            continue
        explanation = _explain_category_change(
            cat_diff, prev_run, curr_run, capability_history or []
        )
        if explanation:
            explanations.append(explanation)

    return explanations


def _explain_category_change(
    cat_diff: Dict[str, Any],
    prev_run: dict,
    curr_run: dict,
    capability_history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    category = cat_diff["category"]
    change = cat_diff["change"]
    is_improvement = change > 0

    causes: List[str] = []
    evidence: List[str] = []
    cap_links: List[str] = []
    graph: List[str] = []

    # Check capability installations between runs
    prev_ts = prev_run.get("timestamp", "")
    curr_ts = curr_run.get("timestamp", "")
    new_caps = _find_new_capabilities(capability_history, prev_ts, curr_ts)

    for cap in new_caps:
        cap_id = cap.get("cap_id", "")
        reason = cap.get("reason", "")
        if _capability_relevant_to_category(cap_id, category):
            cap_links.append(cap_id)
            graph.append(f"Installed {cap_id}")
            graph.append(f"  ↓")
            graph.append(f"  Reason: {reason or 'gap detected'}")

    # World-level analysis
    prev_worlds = {w.get("world", ""): w for w in prev_run.get("worlds", [])}
    curr_worlds = {w.get("world", ""): w for w in curr_run.get("worlds", [])}

    world_category_map = {
        "Memory": ["KnowledgeWorld", "ResearchWorld"],
        "Planning": ["ProjectWorld", "AssistantWorld"],
        "Trust": ["TrustWorld"],
        "Adaptation": ["ResearchWorld", "AssistantWorld"],
        "Coordination": ["MultiAgentWorld"],
        "Evolution": ["EvolutionWorld"],
        "Learning": ["KnowledgeWorld"],
    }

    for wname in world_category_map.get(category, []):
        pw = prev_worlds.get(wname)
        cw = curr_worlds.get(wname)
        if pw and cw:
            pscore = pw.get("overall_score", 0) or 0
            cscore = cw.get("overall_score", 0) or 0
            wdiff = round(cscore - pscore, 1)
            if abs(wdiff) > 2:
                graph.append(f"  {wname}: {pscore} → {cscore}")
                graph.append(f"  ↓")
                graph.append(f"  {'Improved' if wdiff > 0 else 'Declined'} by {abs(wdiff)} pts")
                evidence.append(f"{wname} changed by {wdiff:+.1f} pts")

                # Check metric-level changes
                prev_metrics = pw.get("metrics", {})
                curr_metrics = cw.get("metrics", {})
                for mk in set(list(prev_metrics.keys()) + list(curr_metrics.keys())):
                    pv = prev_metrics.get(mk, 0) or 0
                    cv = curr_metrics.get(mk, 0) or 0
                    if abs(cv - pv) >= 5:
                        graph.append(f"    {mk}: {pv} → {cv}")
                        if cv > pv:
                            causes.append(f"Increased {mk} ({pv}→{cv})")
                        else:
                            causes.append(f"Decreased {mk} ({pv}→{cv})")

    if not causes and not cap_links:
        return None

    direction = "improved" if is_improvement else "regressed"
    return {
        "category": category,
        "direction": direction,
        "change": change,
        "causes": causes,
        "capability_links": cap_links,
        "evidence": evidence,
        "causal_graph": graph if graph else None,
    }


def _find_new_capabilities(
    capability_history: List[Dict[str, Any]],
    since_timestamp: str,
    until_timestamp: str,
) -> List[Dict[str, Any]]:
    if not capability_history:
        return []
    return [
        cap for cap in capability_history
        if since_timestamp < cap.get("timestamp", "") <= until_timestamp
        and cap.get("event_type") == "installation"
    ]


_CAPABILITY_CATEGORY_MAP = {
    "github": ["Research", "Planning"],
    "weather": ["Research"],
    "calc": ["Planning", "Research"],
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

_REVERSE_CATEGORY_MAP: Dict[str, List[str]] = {}
for cap_id, cats in _CAPABILITY_CATEGORY_MAP.items():
    for cat in cats:
        _REVERSE_CATEGORY_MAP.setdefault(cat, []).append(cap_id)


def _capability_relevant_to_category(cap_id: str, category: str) -> bool:
    return cap_id in _CAPABILITY_CATEGORY_MAP and category in _CAPABILITY_CATEGORY_MAP[cap_id]
