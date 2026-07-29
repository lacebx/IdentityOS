from __future__ import annotations

from typing import Any, Dict, List, Optional


def detect_regressions(
    trends: List[Dict[str, Any]],
    consecutive_threshold: int = 3,
    min_change: float = 2.0,
) -> List[Dict[str, Any]]:
    if len(trends) < consecutive_threshold:
        return []

    sorted_trends = sorted(trends, key=lambda x: x.get("timestamp", ""))
    metrics = _collect_metric_names(sorted_trends)

    signals: List[Dict[str, Any]] = []
    for metric in metrics:
        values = [t.get(metric, 0) or 0 for t in sorted_trends]
        consecutive_decreases = 0
        regression_start = None
        for i in range(1, len(values)):
            if values[i] < values[i - 1] - min_change:
                if consecutive_decreases == 0:
                    regression_start = i - 1
                consecutive_decreases += 1
            else:
                if consecutive_decreases >= consecutive_threshold:
                    causes = _likely_causes(metric)
                    signals.append({
                        "metric": metric,
                        "consecutive_decreases": consecutive_decreases,
                        "regression_run_count": i,
                        "start_value": values[regression_start] if regression_start is not None else None,
                        "current_value": values[i - 1],
                        "likely_causes": causes,
                        "severity": _severity(consecutive_decreases, values[i - 1] if i - 1 < len(values) else values[-1]),
                    })
                consecutive_decreases = 0
                regression_start = None

        if consecutive_decreases >= consecutive_threshold:
            causes = _likely_causes(metric)
            signals.append({
                "metric": metric,
                "consecutive_decreases": consecutive_decreases,
                "regression_run_count": len(values),
                "start_value": values[regression_start] if regression_start is not None else None,
                "current_value": values[-1],
                "likely_causes": causes,
                "severity": _severity(consecutive_decreases, values[-1]),
            })

    return signals


def _collect_metric_names(trends: List[Dict[str, Any]]) -> List[str]:
    exclude = {"timestamp", "runs", "identity_id"}
    names: set = set()
    for t in trends:
        names.update(k for k in t.keys() if k not in exclude)
    return sorted(names)


def _likely_causes(metric: str) -> List[str]:
    metric_lower = metric.lower()
    if "memory" in metric_lower or "recall" in metric_lower:
        return ["Context may be exceeding token budget", "Older memories being dropped", "Session contamination"]
    if "plan" in metric_lower or "deadline" in metric_lower or "completion" in metric_lower:
        return ["Scheduled tasks not being revisited", "Capability may be unavailable", "Timeline inconsistency"]
    if "trust" in metric_lower or "hallucination" in metric_lower:
        return ["Stale knowledge not being detected", "Verification rate decreased", "Confidence calibration drift"]
    if "evolution" in metric_lower or "install" in metric_lower or "gap" in metric_lower:
        return ["Registry search quality degraded", "Trust verification blocking legitimate caps", "Retry handler failures"]
    if "adapt" in metric_lower or "belief" in metric_lower:
        return ["Corrective feedback not being incorporated", "Proactive verification declining"]
    if "coordination" in metric_lower or "leakage" in metric_lower or "handoff" in metric_lower:
        return ["Responsibility boundaries weakening", "Memory leakage between agents"]
    return ["Metric-specific cause analysis not available"]


def _severity(consecutive_decreases: int, current_value: float) -> str:
    if consecutive_decreases >= 5 or current_value < 30:
        return "CRITICAL"
    if consecutive_decreases >= 3 or current_value < 50:
        return "WARNING"
    return "INFO"


def format_regression_warning(signal: Dict[str, Any]) -> str:
    severity_tag = {
        "CRITICAL": "!!",
        "WARNING": "!",
        "INFO": "i",
    }.get(signal.get("severity", "INFO"), "?")

    lines = [
        f"  [{severity_tag}] {signal['metric']} has decreased for "
        f"{signal['consecutive_decreases']} consecutive runs.",
        f"      Current value: {signal['current_value']}",
    ]
    if signal.get("start_value") is not None:
        lines.append(f"      Regression started at: {signal['start_value']}")

    causes = signal.get("likely_causes", [])
    if causes:
        lines.append(f"      Likely causes:")
        for c in causes:
            lines.append(f"        • {c}")

    return "\n".join(lines)
