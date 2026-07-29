from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identitybench.storage import BenchmarkStorage


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
    lines.append(f"  Identity:   {CYAN}{identity}{RESET}")
    lines.append(f"  Timestamp:   {ts}")
    lines.append(f"  Duration:    {elapsed}s")
    lines.append(f"")
    lines.append(f"  {BOLD}Overall Score:{RESET} {_color_score(overall)} {_bar(overall)}")
    lines.append(f"")

    cat_scores = run_data.get("category_scores", {})
    lines.append(f"  {BOLD}Category Scores{RESET}")
    lines.append(f"  {'-'*40}")
    for cat in ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning"]:
        score = cat_scores.get(cat, 0)
        lines.append(f"    {cat:20s} {_color_score(score):>6s}  {_bar(score)}")
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

    if trend_data and len(trend_data) >= 2:
        lines.append(f"  {BOLD}Trend Analysis{RESET}")
        lines.append(f"  {'-'*40}")
        sorted_trends = sorted(trend_data, key=lambda x: x.get("timestamp", ""))
        header = f"    {'Run':>5s}  {'Date':>12s}  {'Overall':>8s}  "
        for cat in ["Memory", "Planning", "Trust"]:
            header += f"{cat:>10s}  "
        lines.append(header)
        lines.append(f"    {'-'*55}")
        for i, t in enumerate(sorted_trends, 1):
            date_str = t.get("timestamp", "")[:10]
            ov = t.get("overall_score", 0)
            row = f"    {i:>5d}  {date_str:>12s}  {_color_score(ov):>8s}  "
            for cat in ["Memory", "Planning", "Trust"]:
                cs = t.get(cat, 0)
                row += f"{_color_score(cs):>10s}  "
            lines.append(row)

        if len(sorted_trends) >= 2:
            lines.append(f"")
            lines.append(f"  {BOLD}Regression / Improvement Detection{RESET}")
            lines.append(f"  {'-'*40}")
            prev = sorted_trends[-2]
            curr = sorted_trends[-1]
            all_cats = ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning"]
            for cat in all_cats + ["overall_score"]:
                old = prev.get(cat, 0) or 0
                new = curr.get(cat, 0) or 0
                diff = round(new - old, 1)
                symbol = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                label = "Improved" if diff > 0 else ("Regression" if diff < 0 else "Stable")
                color_cat = GREEN if diff >= 0 else RED
                lines.append(
                    f"    {cat:20s} {old:>6.1f} → {new:>6.1f}  "
                    f"{color_cat}{symbol} {diff:>+5.1f}  ({label}){RESET}"
                )
        lines.append(f"")

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


def generate_markdown_report(run_data: dict, trend_data: Optional[List[dict]] = None) -> str:
    lines: List[str] = []
    lines.append("# IdentityBench Report\n")
    identity = run_data.get("identity_id", "unknown")
    ts = run_data.get("timestamp", "unknown")
    overall = run_data.get("overall_score", 0)
    lines.append(f"**Identity:** `{identity}`  ")
    lines.append(f"**Timestamp:** {ts}  ")
    lines.append(f"**Overall Score:** {overall}/100  \n")
    lines.append("## Category Scores\n")
    lines.append("| Category | Score |")
    lines.append("|----------|-------|")
    cat_scores = run_data.get("category_scores", {})
    for cat in ["Memory", "Planning", "Trust", "Adaptation", "Coordination", "Learning"]:
        score = cat_scores.get(cat, 0)
        lines.append(f"| {cat} | {score}/100 |")
    lines.append("")
    lines.append("## World Results\n")
    lines.append("| World | Overall | Key Metrics |")
    lines.append("|-------|---------|-------------|")
    for w in run_data.get("worlds", []):
        name = w.get("world", "?")
        score = w.get("overall_score", 0)
        metrics = w.get("metrics", {})
        top_m = "; ".join(f"{k}={v}" for k, v in sorted(metrics.items())[:4])
        lines.append(f"| {name} | {score} | {top_m} |")
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
                diff = round(new - old, 1)
                verdict = "Improved" if diff > 0 else ("Regression" if diff < 0 else "Stable")
                label = "Overall" if cat == "overall_score" else cat
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
                lines.append(f"| {label} | {old} | {new} | {arrow} {diff:+.1f} | {verdict} |")
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
