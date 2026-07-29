from __future__ import annotations

from typing import Any, Dict, List, Optional


def render_ascii_timeline(
    entries: List[Dict[str, Any]],
    width: int = 50,
    max_entries: int = 20,
) -> str:
    if not entries:
        return "  No timeline data available."

    lines: List[str] = []
    lines.append(f"  Timeline ({len(entries)} events)")
    lines.append(f"  {'─' * width}")

    for entry in entries[:max_entries]:
        day = entry.get("day", "?")
        event_type = entry.get("event_type", "")
        desc = entry.get("description", "")
        overall = entry.get("overall_score")
        delta = entry.get("delta")

        day_str = f"Day {day:<3d}"

        if event_type == "benchmark_run":
            bar = _progress_bar(overall or 0, 12)
            lines.append(f"  {day_str} ■ {desc:<30s} {bar} {overall}")
        elif event_type == "score_change":
            arrow = "↑" if delta and delta > 0 else "↓"
            lines.append(f"  {day_str} {arrow} {desc}")
        elif event_type in ("installation", "SUCCEEDED"):
            lines.append(f"  {day_str} ● {desc}")
        elif event_type in ("ROLLED_BACK", "FAILED", "validation_failure"):
            lines.append(f"  {day_str} ╳ {desc}")
        elif event_type == "removal":
            lines.append(f"  {day_str} ○ {desc}")
        else:
            lines.append(f"  {day_str} · {desc}")

    if len(entries) > max_entries:
        lines.append(f"  ... and {len(entries) - max_entries} more")

    return "\n".join(lines)


def _progress_bar(value: float, length: int = 10) -> str:
    filled = int((value / 100) * length)
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)
