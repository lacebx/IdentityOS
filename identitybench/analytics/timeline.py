from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_evolution_timeline(
    run_history: List[Dict[str, Any]],
    capability_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    sorted_runs = sorted(run_history, key=lambda x: x.get("timestamp", ""))
    cap_history = capability_history or []

    prev_cats: Dict[str, float] = {}
    for i, run in enumerate(sorted_runs):
        day = i + 1
        ts = run.get("timestamp", "")[:10]
        overall = run.get("overall_score", 0)
        cats = run.get("category_scores", {})

        entries.append({
            "day": day,
            "timestamp": ts,
            "event_type": "benchmark_run",
            "description": f"Benchmark run #{day}",
            "overall_score": overall,
            "category_scores": dict(cats),
        })

        for cat, score in sorted(cats.items()):
            if cat in prev_cats:
                delta = round(score - prev_cats[cat], 1)
                if abs(delta) >= 2:
                    direction = "improved" if delta > 0 else "declined"
                    entries.append({
                        "day": day,
                        "timestamp": ts,
                        "event_type": "score_change",
                        "description": f"{cat} {direction} by {abs(delta):.1f} pts ({prev_cats[cat]} → {score})",
                        "category": cat,
                        "delta": delta,
                    })

        prev_cats = dict(cats)

    # Add capability events
    for cap_event in cap_history:
        event_type = cap_event.get("event_type", cap_event.get("status", ""))
        cap_id = cap_event.get("cap_id", cap_event.get("chosen_capability", "unknown"))

        description_map = {
            "installation": f"Installed {cap_id}",
            "SUCCEEDED": f"Acquired {cap_id} successfully",
            "ROLLED_BACK": f"{cap_id} install rolled back",
            "FAILED": f"{cap_id} acquisition failed",
            "validation_failure": f"{cap_id} validation failed, rolled back",
            "upgrade": f"Upgraded {cap_id}",
            "removal": f"Removed {cap_id}",
        }

        desc = description_map.get(event_type, f"{event_type}: {cap_id}")
        day_estimate = cap_event.get("installed_day", cap_event.get("tick_offset", None))

        entries.append({
            "day": day_estimate if day_estimate else len(sorted_runs),
            "timestamp": cap_event.get("timestamp", ""),
            "event_type": event_type.lower().replace(" ", "_"),
            "description": desc,
            "capability": cap_id,
        })

    entries.sort(key=lambda e: (e.get("day", 0), _event_priority(e.get("event_type", ""))))

    return entries


def _event_priority(event_type: str) -> int:
    order = {
        "installation": 0,
        "SUCCEEDED": 0,
        "upgrade": 1,
        "benchmark_run": 2,
        "score_change": 3,
        "validation_failure": 4,
        "ROLLED_BACK": 4,
        "FAILED": 4,
        "removal": 5,
    }
    return order.get(event_type, 10)


def format_timeline(entries: List[Dict[str, Any]], max_entries: int = 30) -> str:
    if not entries:
        return "  No evolution data available."

    lines: List[str] = []
    for entry in entries[:max_entries]:
        day = entry.get("day", "?")
        desc = entry.get("description", "")
        event_type = entry.get("event_type", "")
        overall = entry.get("overall_score")
        delta = entry.get("delta")

        prefix = f"  Day {day:<3d}"

        if event_type == "benchmark_run":
            lines.append(f"{prefix}  Benchmark ─── Overall: {overall}")
        elif event_type == "score_change":
            arrow = "▲" if delta and delta > 0 else "▼"
            lines.append(f"{prefix}  {arrow} {desc}")
        elif event_type in ("installation", "SUCCEEDED"):
            lines.append(f"{prefix}  + {desc}")
        elif event_type in ("ROLLED_BACK", "FAILED", "validation_failure"):
            lines.append(f"{prefix}  ✗ {desc}")
        elif event_type == "removal":
            lines.append(f"{prefix}  - {desc}")
        else:
            lines.append(f"{prefix}  · {desc}")

    if len(entries) > max_entries:
        lines.append(f"  ... and {len(entries) - max_entries} more entries")

    return "\n".join(lines)
