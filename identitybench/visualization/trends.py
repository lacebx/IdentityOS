from __future__ import annotations

from typing import Any, Dict, List, Optional


def render_trend_chart(
    trends: List[Dict[str, Any]],
    metrics: Optional[List[str]] = None,
    height: int = 10,
    width: int = 40,
) -> str:
    if not trends:
        return "  No trend data available."

    sorted_trends = sorted(trends, key=lambda x: x.get("timestamp", ""))
    if metrics is None:
        metrics = _detect_metrics(sorted_trends)

    lines: List[str] = []
    for metric in metrics:
        values = [t.get(metric, 0) or 0 for t in sorted_trends]
        if not values:
            continue
        min_v = min(values)
        max_v = max(values)
        range_v = max_v - min_v if max_v > min_v else 1

        lines.append(f"  {metric}:")
        for row in range(height, 0, -1):
            threshold = min_v + (range_v * row / height)
            bar = ""
            for v in values:
                if v >= threshold:
                    bar += "█"
                else:
                    bar += " "
            lines.append(f"  {threshold:>5.0f} {bar}")

        # X axis
        labels = []
        for i, _ in enumerate(values):
            if i == 0 or i == len(values) - 1 or (len(values) <= 10):
                labels.append(str(i + 1))
            else:
                labels.append(" ")
        lines.append(f"       {''.join(l for l in labels)}")
        lines.append(f"       {'^' * len(values)} run")
        lines.append(f"       min={min_v:.0f}  max={max_v:.0f}  latest={values[-1]:.0f}")
        lines.append("")

    return "\n".join(lines)


def _detect_metrics(trends: List[Dict[str, Any]]) -> List[str]:
    exclude = {"timestamp", "runs", "identity_id"}
    return [k for k in trends[0].keys() if k not in exclude][:5]
