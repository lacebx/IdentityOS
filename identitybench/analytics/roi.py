from __future__ import annotations

from typing import Any, Dict, List, Optional


def calculate_capability_roi(
    capability_history: List[Dict[str, Any]],
    run_history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not capability_history:
        return []

    caps_by_id: Dict[str, Dict[str, Any]] = {}
    for entry in capability_history:
        cap_id = entry.get("cap_id", entry.get("chosen_capability", "unknown"))
        event_type = entry.get("event_type", entry.get("status", ""))

        if cap_id not in caps_by_id:
            caps_by_id[cap_id] = {
                "cap_id": cap_id,
                "name": entry.get("chosen_capability", entry.get("cap_id", cap_id)),
                "author": entry.get("chosen_author", ""),
                "version": entry.get("chosen_version", ""),
                "installed_day": None,
                "reason": "",
                "events": [],
                "uses": 0,
                "successful_uses": 0,
                "failures": 0,
                "contribution": {},
            }

        cap = caps_by_id[cap_id]

        if event_type == "installation" or entry.get("installation_success"):
            if cap["installed_day"] is None:
                cap["installed_day"] = entry.get("tick_offset", entry.get("installed_day"))

        if entry.get("installation_success"):
            cap["events"].append(entry)
        elif entry.get("retry_success"):
            cap["uses"] += 1
            cap["successful_uses"] += 1
        elif event_type in ("failed", "validation_failure"):
            cap["failures"] += 1

    if run_history:
        _estimate_contribution(caps_by_id, run_history)

    results = []
    for cap_id in sorted(caps_by_id.keys()):
        cap = caps_by_id[cap_id]
        if cap["uses"] == 0 and cap["failures"] == 0:
            cap["recommendation"] = "ARCHIVE_CANDIDATE"
        elif cap["successful_uses"] > 0 and cap["failures"] <= cap["successful_uses"] * 0.3:
            cap["recommendation"] = "KEEP"
        elif cap["failures"] > cap["successful_uses"]:
            cap["recommendation"] = "REMOVE"
        else:
            cap["recommendation"] = "MONITOR"
        results.append(cap)

    return results


def _estimate_contribution(
    caps_by_id: Dict[str, Dict[str, Any]],
    run_history: List[Dict[str, Any]],
) -> None:
    cap_category_map = {
        "github": ["Research", "Planning"],
        "weather": ["Research"],
        "calc": ["Planning", "Research"],
        "web": ["Research", "Trust"],
        "datetime": ["Planning"],
        "filesystem": ["Memory", "Research"],
        "text": ["Adaptation", "Research"],
        "system_info": ["Trust"],
    }

    if len(run_history) < 2:
        return

    sorted_runs = sorted(run_history, key=lambda x: x.get("timestamp", ""))
    first = sorted_runs[0].get("category_scores", {})
    last = sorted_runs[-1].get("category_scores", {})

    for cap_id, cap_entry in caps_by_id.items():
        if cap_entry["uses"] == 0:
            continue
        contribution: Dict[str, float] = {}
        relevant = cap_category_map.get(cap_id, [])
        for cat in relevant:
            old = first.get(cat, 0) or 0
            new = last.get(cat, 0) or 0
            diff = round(new - old, 1)
            if diff > 0:
                share = min(diff, cap_entry["uses"] * 0.5)
                contribution[cat] = round(share, 1)
        cap_entry["contribution"] = contribution


def format_roi_entry(entry: Dict[str, Any]) -> str:
    lines: List[str] = []
    cap_id = entry.get("cap_id", "?")
    lines.append(f"  {cap_id}")
    if entry.get("installed_day"):
        lines.append(f"    Installed: Day {entry['installed_day']}")
    if entry.get("reason"):
        lines.append(f"    Reason: {entry['reason']}")
    lines.append(f"    Uses: {entry.get('uses', 0)}")
    lines.append(f"    Successful uses: {entry.get('successful_uses', 0)}")
    lines.append(f"    Failures: {entry.get('failures', 0)}")

    contrib = entry.get("contribution", {})
    if contrib:
        contrib_str = ", ".join(f"{k}: +{v}" for k, v in sorted(contrib.items()))
        lines.append(f"    Contribution: {contrib_str}")

    rec = entry.get("recommendation", "KEEP")
    tag = {"KEEP": "✓", "ARCHIVE_CANDIDATE": "↓", "REMOVE": "✗", "MONITOR": "~"}.get(rec, "?")
    lines.append(f"    Recommendation: {tag} {rec}")
    return "\n".join(lines)
