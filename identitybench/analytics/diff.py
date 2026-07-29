from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def compute_benchmark_diff(
    prev_run: dict,
    curr_run: dict,
    threshold: float = 3.0,
) -> Dict[str, Any]:
    prev_cats = prev_run.get("category_scores", {})
    curr_cats = curr_run.get("category_scores", {})
    all_cats = sorted(set(list(prev_cats.keys()) + list(curr_cats.keys())))

    prev_worlds = {w.get("world", ""): w for w in prev_run.get("worlds", [])}
    curr_worlds = {w.get("world", ""): w for w in curr_run.get("worlds", [])}
    all_worlds = sorted(set(list(prev_worlds.keys()) + list(curr_worlds.keys())))

    category_diffs: List[Dict[str, Any]] = []
    for cat in all_cats:
        old = prev_cats.get(cat, 0) or 0
        new = curr_cats.get(cat, 0) or 0
        change = round(new - old, 1)
        reasons = _generate_category_reasons(cat, change, prev_run, curr_run)
        if change > threshold:
            verdict = "IMPROVED"
        elif change < -threshold:
            verdict = "REGRESSION"
        else:
            verdict = "STABLE"
        category_diffs.append({
            "category": cat,
            "previous": old,
            "current": new,
            "change": change,
            "verdict": verdict,
            "reasons": reasons,
        })

    world_diffs: List[Dict[str, Any]] = []
    for w in all_worlds:
        pw = prev_worlds.get(w, {})
        cw = curr_worlds.get(w, {})
        old = pw.get("overall_score", 0) or 0
        new = cw.get("overall_score", 0) or 0
        change = round(new - old, 1)
        if abs(change) >= threshold:
            prev_metrics = pw.get("metrics", {})
            curr_metrics = cw.get("metrics", {})
            changed_metrics = {
                k: {"from": prev_metrics.get(k, 0), "to": curr_metrics.get(k, 0)}
                for k in set(list(prev_metrics.keys()) + list(curr_metrics.keys()))
                if abs((curr_metrics.get(k, 0) or 0) - (prev_metrics.get(k, 0) or 0)) >= threshold
            }
            world_diffs.append({
                "world": w,
                "previous": old,
                "current": new,
                "change": change,
                "changed_metrics": changed_metrics,
            })

    prev_overall = prev_run.get("overall_score", 0) or 0
    curr_overall = curr_run.get("overall_score", 0) or 0
    overall_change = round(curr_overall - prev_overall, 1)

    return {
        "overall": {
            "previous": prev_overall,
            "current": curr_overall,
            "change": overall_change,
        },
        "categories": category_diffs,
        "worlds": world_diffs,
        "threshold": threshold,
        "prev_timestamp": prev_run.get("timestamp", ""),
        "curr_timestamp": curr_run.get("timestamp", ""),
    }


def _generate_category_reasons(
    category: str,
    change: float,
    prev_run: dict,
    curr_run: dict,
) -> List[str]:
    reasons: List[str] = []
    if abs(change) < 1.0:
        return reasons

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
    relevant_worlds = world_category_map.get(category, [])

    for wname in relevant_worlds:
        pw = prev_worlds.get(wname)
        cw = curr_worlds.get(wname)
        if pw and cw:
            pscore = pw.get("overall_score", 0) or 0
            cscore = cw.get("overall_score", 0) or 0
            wdiff = round(cscore - pscore, 1)
            if wdiff > 2:
                reasons.append(f"{wname} world improved by {wdiff:+.1f} pts")
            elif wdiff < -2:
                reasons.append(f"{wname} world declined by {wdiff:+.1f} pts")

    if change > 0:
        if category == "Memory":
            reasons.append("Recall accuracy increased")
        elif category == "Planning":
            reasons.append("More scheduled tasks completed")
        elif category == "Trust":
            reasons.append("Hallucination rate decreased")
        elif category == "Evolution":
            reasons.append("Capability acquisition success rate improved")
    elif change < 0:
        if category == "Memory":
            reasons.append("Older memories may have been dropped")
        elif category == "Planning":
            reasons.append("Some scheduled tasks were missed")
        elif category == "Trust":
            reasons.append("Stale knowledge detected more frequently")
        elif category == "Evolution":
            reasons.append("Capability acquisition or retry success declined")

    if not reasons:
        prev_metrics = {}
        curr_metrics = {}
        for w in [prev_run, curr_run]:
            for wdata in w.get("worlds", []):
                wn = wdata.get("world", "")
                if wn in relevant_worlds:
                    if w is prev_run:
                        prev_metrics.update(wdata.get("metrics", {}))
                    else:
                        curr_metrics.update(wdata.get("metrics", {}))
        for k in set(list(prev_metrics.keys()) + list(curr_metrics.keys())):
            pv = prev_metrics.get(k, 0) or 0
            cv = curr_metrics.get(k, 0) or 0
            if abs(cv - pv) >= 5:
                direction = "increased" if cv > pv else "decreased"
                reasons.append(f"Metric '{k}' {direction} from {pv} to {cv}")

    return reasons


def format_diff(diff: Dict[str, Any]) -> str:
    lines: List[str] = []

    ov = diff["overall"]
    arrow = "▲" if ov["change"] > 0 else ("▼" if ov["change"] < 0 else "─")
    lines.append(f"  Overall: {ov['previous']} → {ov['current']} ({arrow}{ov['change']:+g})")

    improved = [c for c in diff["categories"] if c["verdict"] == "IMPROVED"]
    regressed = [c for c in diff["categories"] if c["verdict"] == "REGRESSION"]
    stable = [c for c in diff["categories"] if c["verdict"] == "STABLE"]

    if improved:
        lines.append(f"\n  ▲ Improvements:")
        for c in improved:
            lines.append(f"    {c['category']:20s} {c['previous']} → {c['current']} ({c['change']:+g})")
            for r in c["reasons"][:3]:
                lines.append(f"      • {r}")

    if regressed:
        lines.append(f"\n  ▼ Regressions:")
        for c in regressed:
            lines.append(f"    {c['category']:20s} {c['previous']} → {c['current']} ({c['change']:+g})")
            for r in c["reasons"][:3]:
                lines.append(f"      • {r}")

    if diff["worlds"]:
        lines.append(f"\n  World Changes:")
        for w in diff["worlds"]:
            arrow = "▲" if w["change"] > 0 else "▼"
            lines.append(f"    {w['world']:20s} {w['previous']} → {w['current']} ({arrow}{w['change']:+g})")
            for mk, mv in list(w.get("changed_metrics", {}).items())[:3]:
                lines.append(f"      {mk}: {mv['from']} → {mv['to']}")

    if not improved and not regressed and not diff["worlds"]:
        lines.append(f"\n  No significant changes (threshold: {diff['threshold']} pts).")

    return "\n".join(lines)
