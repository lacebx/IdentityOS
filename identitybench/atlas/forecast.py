from __future__ import annotations

from typing import Any, Dict, List, Optional

from identitybench.atlas.health import compute_identity_health
from identitybench.atlas.weighting import FORECAST_DECAY


def build_forecast(
    category_scores: Dict[str, float],
    predictions: List[Dict[str, Any]],
    weeks: int = 8,
) -> List[Dict[str, Any]]:
    if not predictions:
        return []

    forecast: List[Dict[str, Any]] = []
    prediction_map: Dict[str, Dict[str, Any]] = {
        p["category"]: p for p in predictions
    }

    for week in range(1, weeks + 1):
        decay_factor = 1.0 - (FORECAST_DECAY * week)
        projected_scores: Dict[str, float] = {}
        for cat, current in category_scores.items():
            pred = prediction_map.get(cat)
            if pred and pred.get("data_points", 0) >= 2:
                slope = pred.get("slope", 0.0)
                projected = current + slope * week * decay_factor
                projected_scores[cat] = round(max(0.0, min(projected, 100.0)), 1)
            else:
                projected_scores[cat] = current

        health_result = compute_identity_health(
            category_scores=projected_scores,
        )
        deltas: Dict[str, float] = {}
        if forecast:
            prev = forecast[-1]
            for cat, val in projected_scores.items():
                prev_val = prev["projected_scores"].get(cat, val)
                deltas[cat] = round(val - prev_val, 1)
        else:
            for cat, val in projected_scores.items():
                deltas[cat] = 0.0

        forecast.append({
            "week": week,
            "projected_health": health_result["health"],
            "projected_scores": projected_scores,
            "deltas": deltas,
            "health_confidence": health_result["confidence"],
        })

    return forecast


def format_forecast(
    forecast: List[Dict[str, Any]],
    detail_categories: Optional[List[str]] = None,
) -> str:
    if not forecast:
        return "  No forecast data available."

    detail_cats = detail_categories or ["Research", "Planning", "Trust"]

    header = "  Forecast Timeline:\n"
    header += f"  {'Week':>6s}  {'Health':>7s}"
    for cat in detail_cats:
        header += f"  {cat:>12s}"
    header += "\n"
    header += "  " + "-" * (6 + 9 + 14 * len(detail_cats))

    rows = []
    for entry in forecast:
        row = f"  {entry['week']:>4d} +  {entry['projected_health']:>6.1f}"
        for cat in detail_cats:
            val = entry["projected_scores"].get(cat, 0)
            delta = entry["deltas"].get(cat, 0)
            delta_str = f"{delta:+.0f}" if delta != 0 else " 0"
            row += f"  {val:>5.1f} ({delta_str:>3s})"
        rows.append(row)

    return header + "\n" + "\n".join(rows)
