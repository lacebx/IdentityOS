from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identitybench.storage import BenchmarkStorage
from identitybench.analytics.diff import compute_benchmark_diff, format_diff
from identitybench.analytics.regression import detect_regressions, format_regression_warning
from identitybench.analytics.recommendations import generate_recommendations, format_recommendations
from identitybench.analytics.roi import calculate_capability_roi, format_roi_entry
from identitybench.analytics.root_cause import analyze_root_causes
from identitybench.analytics.timeline import build_evolution_timeline, format_timeline
from identitybench.visualization.timeline import render_ascii_timeline
from identitybench.visualization.trends import render_trend_chart


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _color_score(score: float) -> str:
    if score >= 80:
        return f"{GREEN}{score}{RESET}"
    if score >= 60:
        return f"{YELLOW}{score}{RESET}"
    return f"{RED}{score}{RESET}"


def _bar(score: float, width: int = 30) -> str:
    filled = int((score / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if score >= 80 else (YELLOW if score >= 60 else RED)
    return f"{color}{bar}{RESET}"


def _format_change(score: float, prev: Optional[float]) -> str:
    if prev is None:
        return f"{_color_score(score)}"
    diff = round(score - prev, 1)
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
    return f"{_color_score(score)} ({arrow}{diff:+g})"


def generate_report_text(
    run_data: dict,
    trend_data: Optional[List[dict]] = None,
    comparison_data: Optional[Dict[str, dict]] = None,
) -> str:
    lines: List[str] = []
    lines.append(f"{BOLD}{'='*60}{RESET}")
    lines.append(f"{BOLD}  IdentityBench Report{RESET}")
    lines.append(f"{BOLD}{'='*60}{RESET}")
    ts = run_data.get("timestamp", "unknown")
    identity = run_data.get("identity_id", "unknown")
    overall = run_data.get("overall_score", 0)
    elapsed = run_data.get("elapsed_seconds", 0)
    prev_run_data = _find_previous_run(run_data, trend_data)
    prev_overall = prev_run_data.get("overall_score") if prev_run_data else None
    lines.append(f"  Identity:   {CYAN}{identity}{RESET}")
    lines.append(f"  Timestamp:   {ts}")
    lines.append(f"  Duration:    {elapsed}s")
    lines.append(f"")
    overall_str = _format_change(overall, prev_overall)
    lines.append(f"  {BOLD}Overall Score:{RESET} {overall_str} {_bar(overall)}")
    lines.append(f"")

    cat_scores = run_data.get("category_scores", {})
    prev_cats = prev_run_data.get("category_scores", {}) if prev_run_data else {}
    explanations = run_data.get("explanations", {})
    lines.append(f"  {BOLD}Category Scores{RESET}")
    lines.append(f"  {'-'*40}")
    for cat in ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning", "Evolution"]:
        score = cat_scores.get(cat, 0)
        prev = prev_cats.get(cat)
        score_str = _format_change(score, prev)
        lines.append(f"    {cat:20s} {score_str:>20s}  {_bar(score)}")
        exp = explanations.get(cat, {})
        reasons = exp.get("reasons", [])
        conf = exp.get("confidence", 0)
        if reasons:
            for r in reasons[:3]:
                symbol = "✓" if not r.startswith("hallucinated") and not r.startswith("failed") and not r.startswith("missed") else "✗"
                lines.append(f"      {symbol} {r}")
            if conf:
                lines.append(f"      Confidence: {conf:.2f}")
    lines.append(f"")

    worlds = run_data.get("worlds", [])
    if worlds:
        lines.append(f"  {BOLD}World Results{RESET}")
        lines.append(f"  {'-'*40}")
        for w in worlds:
            name = w.get("world", "?")
            score = w.get("overall_score", 0)
            metrics = w.get("metrics", {})
            top_metrics = ", ".join(
                f"{k}={v}" for k, v in sorted(metrics.items())[:4]
            )
            lines.append(f"    {name:20s} {_color_score(score):>6s}  ({top_metrics})")
        lines.append(f"")

    # Diff section
    diff = run_data.get("diff_vs_previous")
    if diff:
        lines.append(f"  {BOLD}Benchmark Diff{RESET}")
        lines.append(f"  {'-'*40}")
        lines.append(format_diff(diff))
        lines.append(f"")

    # Root cause analysis
    root_causes = run_data.get("root_causes", [])
    if root_causes:
        lines.append(f"  {BOLD}Root Cause Analysis{RESET}")
        lines.append(f"  {'-'*40}")
        for rc in root_causes:
            direction = rc.get("direction", "changed")
            cat = rc.get("category", "?")
            change = rc.get("change", 0)
            arrow = "▲" if change > 0 else "▼"
            lines.append(f"    {cat} {direction} ({arrow}{change:+g})")
            graph = rc.get("causal_graph", [])
            if graph:
                for g in graph[:6]:
                    lines.append(f"      {g}")
        lines.append(f"")

    # Trend analysis
    if trend_data and len(trend_data) >= 2:
        lines.append(f"  {BOLD}Trend Analysis{RESET}")
        lines.append(f"  {'-'*40}")
        sorted_trends = sorted(trend_data, key=lambda x: x.get("timestamp", ""))
        header = f"    {'Run':>5s}  {'Date':>12s}  {'Overall':>8s}  "
        for cat in ["Memory", "Planning", "Trust", "Evolution"]:
            header += f"{cat:>10s}  "
        lines.append(header)
        lines.append(f"    {'-'*70}")
        for i, t in enumerate(sorted_trends, 1):
            date_str = t.get("timestamp", "")[:10]
            ov = t.get("overall_score", 0)
            row = f"    {i:>5d}  {date_str:>12s}  {_color_score(ov):>8s}  "
            for cat in ["Memory", "Planning", "Trust", "Evolution"]:
                cs = t.get(cat, 0)
                row += f"{_color_score(cs):>10s}  "
            lines.append(row)

        if len(sorted_trends) >= 2:
            lines.append(f"")
            lines.append(f"  {BOLD}Regression / Improvement Detection{RESET}")
            lines.append(f"  {'-'*40}")
            prev = sorted_trends[-2]
            curr = sorted_trends[-1]
            all_cats = ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning", "Evolution"]
            for cat in all_cats + ["overall_score"]:
                old = prev.get(cat, 0) or 0
                new = curr.get(cat, 0) or 0
                diff_pt = round(new - old, 1)
                symbol = "▲" if diff_pt > 0 else ("▼" if diff_pt < 0 else "─")
                label = "Improved" if diff_pt > 0 else ("Regression" if diff_pt < 0 else "Stable")
                color_cat = GREEN if diff_pt >= 0 else RED
                lines.append(
                    f"    {cat:20s} {old:>6.1f} → {new:>6.1f}  "
                    f"{color_cat}{symbol} {diff_pt:>+5.1f}  ({label}){RESET}"
                )
        lines.append(f"")

    # Regression warnings
    regressions = run_data.get("regressions", [])
    if regressions:
        lines.append(f"  {BOLD}Regression Warnings{RESET}")
        lines.append(f"  {'-'*40}")
        for sig in regressions[:3]:
            lines.append(format_regression_warning(sig))
            lines.append("")

    # Recommendations
    recs = run_data.get("recommendations", [])
    if recs:
        lines.append(f"  {BOLD}Recommendations{RESET}")
        lines.append(f"  {'-'*40}")
        lines.append(format_recommendations(recs))
        lines.append(f"")

    # Timeline
    timeline = build_evolution_timeline(
        trend_data or [],
        _load_capability_journal(identity),
    )
    if timeline:
        lines.append(f"  {BOLD}Evolution Timeline{RESET}")
        lines.append(f"  {'-'*40}")
        lines.append(render_ascii_timeline(timeline, max_entries=12))
        lines.append(f"")

    # Comparison
    if comparison_data:
        lines.append(f"  {BOLD}Identity Comparison{RESET}")
        lines.append(f"  {'-'*40}")
        ids = list(comparison_data.keys())
        cats_to_show = ["Overall"] + list(cat_scores.keys())
        header = f"    {'Metric':20s}"
        for id_ in ids:
            header += f"  {id_:>15s}"
        lines.append(header)
        lines.append(f"    {'-' * (22 + 17 * len(ids))}")
        for cat in cats_to_show:
            row = f"    {cat:20s}"
            for id_ in ids:
                data = comparison_data[id_]
                if cat == "Overall":
                    val = data.get("overall_score", 0)
                else:
                    val = data.get("category_scores", {}).get(cat, 0)
                row += f"  {_color_score(val):>15s}"
            lines.append(row)
        lines.append(f"")

    # Simple legacy recommendations for backward compat
    if not recs:
        lines.append(f"  {BOLD}Recommendations{RESET}")
        lines.append(f"  {'-'*40}")
        weakest = sorted(cat_scores.items(), key=lambda x: x[1])
        for cat, score in weakest[:3]:
            if score < 70:
                lines.append(f"    {RED}⚠ {cat} ({score}) needs improvement{RESET}")
        strongest = sorted(cat_scores.items(), key=lambda x: -x[1])
        for cat, score in strongest[:2]:
            if score >= 80:
                lines.append(f"    {GREEN}✓ {cat} ({score}) is strong{RESET}")
        if all(s >= 80 for s in cat_scores.values()):
            lines.append(f"    {GREEN}✓ All categories are performing well!{RESET}")
        lines.append(f"")

    lines.append(f"{BOLD}{'='*60}{RESET}")
    return "\n".join(lines)


def _find_previous_run(run_data: dict, trend_data: Optional[List[dict]]) -> Optional[dict]:
    if not trend_data or len(trend_data) < 2:
        return None
    sorted_trends = sorted(trend_data, key=lambda x: x.get("timestamp", ""))
    prev = sorted_trends[-2]
    return {"category_scores": {k: v for k, v in prev.items() if k != "timestamp"}, "overall_score": prev.get("overall_score", 0)}


def _load_capability_journal(identity_id: str) -> List[dict]:
    from identitybench.journal.capability_journal import CapabilityJournal
    journal = CapabilityJournal()
    caps = journal.list_capabilities(identity_id)
    entries = []
    for cap_id in caps:
        entries.extend(journal.get_journal(identity_id, cap_id))
    return entries


def generate_markdown_report(run_data: dict, trend_data: Optional[List[dict]] = None) -> str:
    lines: List[str] = []
    lines.append("# IdentityBench Report\n")
    identity = run_data.get("identity_id", "unknown")
    ts = run_data.get("timestamp", "unknown")
    overall = run_data.get("overall_score", 0)
    prev = _find_previous_run(run_data, trend_data)
    prev_overall = prev.get("overall_score") if prev else None
    overall_str = f"{overall}"
    if prev_overall is not None:
        diff = round(overall - prev_overall, 1)
        overall_str += f" ({'+' if diff > 0 else ''}{diff})"
    lines.append(f"**Identity:** `{identity}`  ")
    lines.append(f"**Timestamp:** {ts}  ")
    lines.append(f"**Overall Score:** {overall_str}/100  \n")

    cat_scores = run_data.get("category_scores", {})
    explanations = run_data.get("explanations", {})
    lines.append("## Category Scores\n")
    lines.append("| Category | Score | Explanation |")
    lines.append("|----------|-------|-------------|")
    for cat in ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning", "Evolution"]:
        score = cat_scores.get(cat, 0)
        exp = explanations.get(cat, {})
        reasons = exp.get("reasons", [])
        summary = "; ".join(reasons[:2]) if reasons else "—"
        lines.append(f"| {cat} | {score}/100 | {summary} |")
    lines.append("")

    diff = run_data.get("diff_vs_previous")
    if diff:
        lines.append("## Benchmark Diff\n")
        lines.append("| Category | Previous | Current | Change | Verdict |")
        lines.append("|----------|----------|---------|--------|---------|")
        for c in diff.get("categories", []):
            arrow = "▲" if c["change"] > 0 else ("▼" if c["change"] < 0 else "─")
            lines.append(f"| {c['category']} | {c['previous']} | {c['current']} | {arrow} {c['change']:+.1f} | {c['verdict']} |")

    lines.append("\n## World Results\n")
    lines.append("| World | Overall | Key Metrics |")
    lines.append("|-------|---------|-------------|")
    for w in run_data.get("worlds", []):
        name = w.get("world", "?")
        score = w.get("overall_score", 0)
        metrics = w.get("metrics", {})
        top_m = "; ".join(f"{k}={v}" for k, v in sorted(metrics.items())[:4])
        lines.append(f"| {name} | {score} | {top_m} |")
    lines.append("")

    recs = run_data.get("recommendations", [])
    if recs:
        lines.append("## Recommendations\n")
        for rec in recs[:5]:
            action = rec.get("action", "")
            target = rec.get("target", "")
            impact = rec.get("estimated_impact", "")
            conf = rec.get("confidence", 0)
            evidence = "; ".join(rec.get("evidence", [])[:2])
            lines.append(f"- **[{action}] {target}** (impact: {impact}, confidence: {conf:.0%})")
            if evidence:
                lines.append(f"  - {evidence}")
        lines.append("")

    if trend_data and len(trend_data) >= 2:
        lines.append("## Trend Analysis\n")
        lines.append("| Run | Date | Overall | Memory | Planning | Trust |")
        lines.append("|-----|------|---------|--------|----------|-------|")
        sorted_trends = sorted(trend_data, key=lambda x: x.get("timestamp", ""))
        for i, t in enumerate(sorted_trends, 1):
            date_str = t.get("timestamp", "")[:10]
            ov = t.get("overall_score", 0)
            mem = t.get("Memory", 0)
            plan = t.get("Planning", 0)
            trust = t.get("Trust", 0)
            lines.append(f"| {i} | {date_str} | {ov} | {mem} | {plan} | {trust} |")
        lines.append("")
        if len(sorted_trends) >= 2:
            lines.append("## Regression Analysis\n")
            lines.append("| Metric | Previous | Current | Change | Verdict |")
            lines.append("|--------|----------|---------|--------|---------|")
            prev = sorted_trends[-2]
            curr = sorted_trends[-1]
            for cat in ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning", "overall_score"]:
                old = prev.get(cat, 0) or 0
                new = curr.get(cat, 0) or 0
                diff_pt = round(new - old, 1)
                verdict = "Improved" if diff_pt > 0 else ("Regression" if diff_pt < 0 else "Stable")
                label = "Overall" if cat == "overall_score" else cat
                arrow = "▲" if diff_pt > 0 else ("▼" if diff_pt < 0 else "─")
                lines.append(f"| {label} | {old} | {new} | {arrow} {diff_pt:+.1f} | {verdict} |")

    lines.append("")
    lines.append("## Raw Metrics\n")
    lines.append("```json")
    metrics_summary = {"overall_score": overall, "category_scores": cat_scores}
    lines.append(json.dumps(metrics_summary, indent=2))
    lines.append("```")
    return "\n".join(lines)


def generate_regression_summary(
    prev_run: dict,
    curr_run: dict,
    threshold: float = 5.0,
) -> Dict[str, Any]:
    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    prev_cats = prev_run.get("category_scores", {})
    curr_cats = curr_run.get("category_scores", {})
    all_cats = set(list(prev_cats.keys()) + list(curr_cats.keys()))
    for cat in sorted(all_cats):
        old = prev_cats.get(cat, 0) or 0
        new = curr_cats.get(cat, 0) or 0
        diff = round(new - old, 1)
        entry = {"category": cat, "previous": old, "current": new, "change": diff}
        if diff < -threshold:
            entry["verdict"] = "REGRESSION"
            regressions.append(entry)
        elif diff > threshold:
            entry["verdict"] = "IMPROVED"
            improvements.append(entry)
        else:
            entry["verdict"] = "STABLE"
    prev_overall = prev_run.get("overall_score", 0) or 0
    curr_overall = curr_run.get("overall_score", 0) or 0
    overall_diff = round(curr_overall - prev_overall, 1)
    overall_verdict = "STABLE"
    if overall_diff < -threshold:
        overall_verdict = "REGRESSION"
    elif overall_diff > threshold:
        overall_verdict = "IMPROVED"
    return {
        "overall": {
            "previous": prev_overall,
            "current": curr_overall,
            "change": overall_diff,
            "verdict": overall_verdict,
        },
        "regressions": regressions,
        "improvements": improvements,
        "threshold": threshold,
        "failed": len(regressions) > 0,
    }


def build_comparison_data(storage: BenchmarkStorage, identities: List[str]) -> Dict[str, dict]:
    data: Dict[str, dict] = {}
    for id_ in identities:
        run = storage.load_latest_run(id_)
        if run:
            data[id_] = run
    return data
