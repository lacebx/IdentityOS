from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def _linear_regression(
    values: List[float],
) -> Tuple[float, float, float, int]:
    n = len(values)
    if n < 2:
        return 0.0, values[-1] if values else 0.0, 0.0, n
    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    den = sum((x - x_mean) ** 2 for x in x_vals)
    slope = num / den if den != 0 else 0.0
    intercept = y_mean - slope * x_mean
    y_pred = [slope * x + intercept for x in x_vals]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(values, y_pred))
    ss_tot = sum((y - y_mean) ** 2 for y in values)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    return slope, intercept, r_squared, n


def _estimate_confidence(
    r_squared: float,
    n: int,
    slope: float,
) -> float:
    if n < 3:
        return 0.3
    data_quality = min(n / 15.0, 1.0)
    fit_quality = max(0.0, r_squared)
    trend_strength = min(abs(slope) / 5.0, 1.0) * 0.2
    raw = data_quality * 0.4 + fit_quality * 0.4 + trend_strength
    return round(min(max(raw, 0.1), 0.95), 2)


def _recommendation_for_trend(
    category: str,
    slope: float,
    predicted_value: float,
    current_value: float,
) -> str:
    if slope < -0.5 and predicted_value < current_value:
        if category == "Memory":
            return "Compress episodic memories and prune stale contexts"
        elif category == "Planning":
            return "Review task prioritization and deadline management"
        elif category == "Trust":
            return "Increase verification frequency and refresh knowledge"
        elif category == "Adaptation":
            return "Increase proactive verification and belief updates"
        elif category == "Learning":
            return "Increase pattern recognition exercises"
        elif category == "Evolution":
            return "Expand capability registry and increase acquisition attempts"
        return "Investigate declining trend and apply corrective measures"
    if slope > 0.5:
        return "Continue current approach and monitor for plateau"
    return "Maintain current practices and monitor for changes"


def predict_category_trend(
    category: str,
    historical_values: List[float],
    steps_ahead: int = 5,
) -> Dict[str, Any]:
    if not historical_values:
        return {
            "category": category,
            "current_value": 0.0,
            "predicted_value": 0.0,
            "confidence": 0.0,
            "trend_direction": "unknown",
            "slope": 0.0,
            "r_squared": 0.0,
            "data_points": 0,
            "evidence": ["No historical data available"],
            "recommended_action": "Run benchmark to establish baseline",
        }
    current_value = historical_values[-1]
    slope, intercept, r_squared, n = _linear_regression(historical_values)
    predicted_value = slope * (n - 1 + steps_ahead) + intercept
    predicted_value = round(max(0.0, min(predicted_value, 100.0)), 1)
    confidence = _estimate_confidence(r_squared, n, slope)
    if slope > 0.3:
        direction = "improving"
    elif slope < -0.3:
        direction = "declining"
    else:
        direction = "stable"
    evidence = []
    if n >= 2:
        evidence.append(
            f"Trend computed from {n} data points"
        )
        if abs(slope) > 0.5:
            evidence.append(
                f"Consistent {'upward' if slope > 0 else 'downward'} trend "
                f"({slope:+.2f} pts/run)"
            )
        if r_squared > 0.7:
            evidence.append("Strong linear fit (R² > 0.7)")
        elif r_squared < 0.3:
            evidence.append("Weak linear fit — values are volatile")
        if direction == "declining" and abs(slope) > 1.0:
            evidence.append(
                f"Declining at {abs(slope):.1f} pts/run — may need intervention"
            )
    action = _recommendation_for_trend(category, slope, predicted_value, current_value)
    return {
        "category": category,
        "current_value": current_value,
        "predicted_value": predicted_value,
        "confidence": confidence,
        "trend_direction": direction,
        "slope": round(slope, 2),
        "r_squared": round(r_squared, 3),
        "data_points": n,
        "evidence": evidence,
        "recommended_action": action,
    }


def predict_all_categories(
    trends: List[Dict[str, Any]],
    steps_ahead: int = 5,
) -> List[Dict[str, Any]]:
    primary_categories = [
        "Memory",
        "Planning",
        "Trust",
        "Adaptation",
        "Learning",
        "Evolution",
    ]
    results = []
    for cat in primary_categories:
        values = []
        for t in trends:
            v = t.get(cat)
            if v is not None:
                values.append(v)
        result = predict_category_trend(cat, values, steps_ahead)
        results.append(result)
    return results


def format_prediction(prediction: Dict[str, Any]) -> str:
    direction_symbols = {
        "improving": "▲",
        "declining": "▼",
        "stable": "─",
        "unknown": "?",
    }
    sym = direction_symbols.get(prediction["trend_direction"], "?")
    lines = [
        f"  {prediction['category']:15s} {sym} "
        f"{prediction['current_value']:.0f} → "
        f"{prediction['predicted_value']:.0f} "
        f"(confidence: {prediction['confidence']:.0%})"
    ]
    if prediction.get("evidence"):
        for e in prediction["evidence"][:2]:
            lines.append(f"    • {e}")
    if prediction.get("recommended_action"):
        lines.append(f"    → {prediction['recommended_action']}")
    return "\n".join(lines)
