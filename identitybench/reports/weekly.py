from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identitybench.analytics.diff import compute_benchmark_diff, format_diff
from identitybench.analytics.regression import detect_regressions, format_regression_warning
from identitybench.analytics.recommendations import generate_recommendations, format_recommendations
from identitybench.analytics.roi import calculate_capability_roi, format_roi_entry
from identitybench.analytics.root_cause import analyze_root_causes
from identitybench.analytics.timeline import build_evolution_timeline, format_timeline
from identitybench.journal.evolution_history import EvolutionHistory


def generate_weekly_report(
    identity_id: str,
    run_history: List[Dict[str, Any]],
    capability_history: Optional[List[Dict[str, Any]]] = None,
    fact_counts: Optional[List[int]] = None,
) -> Dict[str, Any]:
    if not run_history:
        return {
            "identity_id": identity_id,
            "error": "No benchmark runs available.",
        }

    sorted_runs = sorted(run_history, key=lambda x: x.get("timestamp", ""))
    latest = sorted_runs[-1]
    prev = sorted_runs[-2] if len(sorted_runs) >= 2 else None

    cat_scores = latest.get("category_scores", {})

    diff = None
    if prev:
        diff = compute_benchmark_diff(prev, latest)

    regressions = detect_regressions(run_history)

    recommendations = generate_recommendations(
        cat_scores=cat_scores,
        trends=run_history,
        regressions=regressions,
        capability_history=capability_history,
    )

    roi = calculate_capability_roi(
        capability_history or [],
        run_history,
    )

    root_causes = []
    if diff and prev:
        root_causes = analyze_root_causes(diff, prev, latest, capability_history)

    timeline = build_evolution_timeline(run_history, capability_history)

    evo = EvolutionHistory()
    learning_effectiveness = evo.compute_learning_vs_evolution(identity_id, fact_counts)

    prometheus_health = evo.compute_prometheus_health(identity_id, capability_history)

    overall = latest.get("overall_score", 0)
    prev_overall = prev.get("overall_score", 0) if prev else 0
    overall_change = round(overall - prev_overall, 1) if prev else 0

    if cat_scores:
        sorted_cats = sorted(cat_scores.items(), key=lambda x: x[1])
        largest_improvement = None
        largest_regression = None
        if diff:
            for c in diff.get("categories", []):
                if c["verdict"] == "IMPROVED" and (largest_improvement is None or c["change"] > largest_improvement["change"]):
                    largest_improvement = c
                if c["verdict"] == "REGRESSION" and (largest_regression is None or c["change"] < largest_regression["change"]):
                    largest_regression = c

    new_caps = [c for c in (capability_history or []) if c.get("event_type") == "installation"]
    unused_caps = [c for c in roi if c.get("recommendation") == "ARCHIVE_CANDIDATE"]

    return {
        "identity_id": identity_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs_completed": len(run_history),
        "overall_score": overall,
        "overall_change": overall_change,
        "category_scores": cat_scores,
        "largest_improvement": largest_improvement,
        "largest_regression": largest_regression,
        "diff": diff,
        "regressions": regressions,
        "recommendations": recommendations,
        "roi": roi,
        "root_causes": root_causes,
        "timeline": timeline[:30],
        "new_capabilities": [c.get("cap_id", c.get("chosen_capability", "?")) for c in new_caps],
        "unused_capabilities": [c.get("cap_id", "?") for c in unused_caps],
        "learning_effectiveness": learning_effectiveness,
        "prometheus_health": prometheus_health,
        "confidence": _compute_confidence(run_history),
    }


def _compute_confidence(run_history: List[Dict[str, Any]]) -> float:
    if len(run_history) < 2:
        return 0.5
    return min(0.95, 0.5 + len(run_history) * 0.025)


def format_weekly_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  IdentityBench Weekly Report")
    lines.append("=" * 60)
    lines.append(f"  Identity:   {report.get('identity_id', '?')}")
    lines.append(f"  Runs:       {report.get('runs_completed', 0)}")
    overall = report.get("overall_score", 0)
    change = report.get("overall_change", 0)
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    lines.append(f"  Overall:    {overall} ({arrow}{change:+g})")
    lines.append(f"  Confidence: {report.get('confidence', 0):.0%}")
    lines.append("")

    # Largest changes
    li = report.get("largest_improvement")
    lr = report.get("largest_regression")
    if li:
        lines.append(f"  Largest Improvement: {li['category']} ({li['change']:+g})")
    if lr:
        lines.append(f"  Largest Regression:  {lr['category']} ({lr['change']:+g})")
    if li or lr:
        lines.append("")

    # Category scores
    cat_scores = report.get("category_scores", {})
    if cat_scores:
        lines.append("  Category Scores:")
        lines.append(f"  {'-'*40}")
        for cat, score in sorted(cat_scores.items(), key=lambda x: -x[1]):
            lines.append(f"    {cat:20s} {score:>6.1f}")
        lines.append("")

    # Diff
    diff = report.get("diff")
    if diff:
        lines.append("  Benchmark Diff:")
        lines.append(f"  {'-'*40}")
        lines.append(format_diff(diff))
        lines.append("")

    # Root causes
    root_causes = report.get("root_causes", [])
    if root_causes:
        lines.append("  Root Cause Analysis:")
        lines.append(f"  {'-'*40}")
        for rc in root_causes:
            direction = rc.get("direction", "changed")
            cat = rc.get("category", "?")
            change = rc.get("change", 0)
            lines.append(f"    {cat} {direction} ({change:+g})")
            graph = rc.get("causal_graph", [])
            if graph:
                for g in graph[:6]:
                    lines.append(f"      {g}")
        lines.append("")

    # New capabilities
    new_caps = report.get("new_capabilities", [])
    if new_caps:
        lines.append(f"  New Capabilities ({len(new_caps)}):")
        for cap in new_caps:
            lines.append(f"    + {cap}")
        lines.append("")

    # Unused capabilities
    unused = report.get("unused_capabilities", [])
    if unused:
        lines.append(f"  Unused Capabilities ({len(unused)}):")
        for cap in unused:
            lines.append(f"    - {cap}")
        lines.append("")

    # ROI
    roi = report.get("roi", [])
    if roi:
        lines.append("  Capability ROI:")
        lines.append(f"  {'-'*40}")
        for entry in roi[:5]:
            lines.append(format_roi_entry(entry))
            lines.append("")

    # Learning vs Evolution
    le = report.get("learning_effectiveness", {})
    if le and le.get("learning_effectiveness") != "N/A":
        lines.append("  Learning vs Evolution:")
        lines.append(f"  {'-'*40}")
        lines.append(f"    Facts learned:     {le.get('facts_learned', 0)}")
        lines.append(f"    Benchmark improvement: {le.get('benchmark_improvement', 0)} pts")
        lines.append(f"    Effectiveness:    {le.get('learning_effectiveness', 'N/A')} ({le.get('effectiveness_score', 0)})")
        lines.append("")

    # Prometheus health
    ph = report.get("prometheus_health", {})
    if ph:
        lines.append("  Prometheus Health:")
        lines.append(f"  {'-'*40}")
        lines.append(f"    Overall Health:  {ph.get('overall_health', 0)}/100")
        lines.append(f"    Gap Detection:   {ph.get('gap_detection_accuracy', 0)}")
        lines.append(f"    Install Rate:    {ph.get('install_success_rate', 0)}%")
        lines.append(f"    Retry Success:   {ph.get('retry_success', 0)}%")
        lines.append("")

    # Regressions
    regressions = report.get("regressions", [])
    if regressions:
        lines.append("  Regression Warnings:")
        lines.append(f"  {'-'*40}")
        for sig in regressions[:3]:
            lines.append(format_regression_warning(sig))
            lines.append("")

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        lines.append("  Recommendations:")
        lines.append(f"  {'-'*40}")
        lines.append(format_recommendations(recs))
        lines.append("")

    # Timeline
    timeline = report.get("timeline", [])
    if timeline:
        lines.append("  Evolution Timeline:")
        lines.append(f"  {'-'*40}")
        lines.append(format_timeline(timeline, max_entries=15))
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
