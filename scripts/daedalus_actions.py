#!/usr/bin/env python3
"""
Daedalus Autonomous Actions — proactive engineering maintenance for IdentityOS.

Daedalus runs periodically (daily/weekly) and:
1. Checks benchmark trends and opens issues for regressions
2. Reviews goal progress and creates initiative proposals
3. Detects stale goals and suggests reprioritization
4. Opens issues for architectural concerns found during analysis
5. Proposes PRs for low-risk improvements (documentation, dependency bumps, etc.)

This is Daedalus's proactive mode — he doesn't wait for PRs to review,
he actively seeks out problems and opportunities.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DAEDALUS_SIGNATURE = "\u2014 Daedalus\nLace's Engineering Partner\nIdentityOS"

GITHUB_TOKEN = os.environ.get("DAEDALUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "lacebx/IdentityOS")


def load_goals() -> Dict[str, Any]:
    path = Path(".daedalus/goals.json")
    if path.exists():
        return json.loads(path.read_text())
    return {"primary_goals": [], "observations": [], "initiatives": []}


def save_goals(goals: Dict[str, Any]) -> None:
    path = Path(".daedalus/goals.json")
    path.write_text(json.dumps(goals, indent=2))
    print(f"Goals updated: {path}")


def load_benchmark_trends() -> Optional[List[Dict[str, Any]]]:
    bench_dir = Path(".identitybench")
    if not bench_dir.exists():
        return None
    trends = []
    for trend_file in bench_dir.rglob("*trend*"):
        if trend_file.suffix == ".json":
            try:
                data = json.loads(trend_file.read_text())
                if isinstance(data, list):
                    trends.extend(data)
                else:
                    trends.append(data)
            except Exception:
                pass
    return trends if trends else None


def check_benchmark_health() -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    trends = load_benchmark_trends()
    if trends is None:
        return findings
    if len(trends) >= 3:
        recent = trends[-3:]
        for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]:
            values = [t.get(cat, t.get("category_scores", {}).get(cat)) for t in recent]
            values = [v for v in values if v is not None]
            if len(values) >= 3 and all(values[i] >= values[i + 1] for i in range(len(values) - 1)):
                findings.append({
                    "type": "declining_trend",
                    "category": cat,
                    "values": values,
                    "message": f"{cat} has been declining for {len(values)} consecutive runs",
                })
    return findings


def check_goal_progress(goals: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    active_goals = [g for g in goals.get("primary_goals", []) if g.get("status") == "active"]
    for goal in active_goals:
        gid = goal.get("id", "")
        gname = goal.get("goal", "")
        priority = goal.get("priority", 0)
        metrics = goal.get("metrics", [])
        if "benchmark" in gname.lower() or "benchmark" in str(metrics).lower():
            trends = load_benchmark_trends()
            if trends is None:
                findings.append({
                    "type": "no_benchmark_data",
                    "goal_id": gid,
                    "message": f"No benchmark data available to track goal: {gname[:60]}",
                })
    return findings


def create_issue(title: str, body: str, labels: Optional[List[str]] = None) -> Optional[int]:
    if not GITHUB_TOKEN:
        print(f"Cannot create issue: no GITHUB_TOKEN set (would create: {title})")
        return None
    labels_str = ""
    if labels:
        labels_str = " ".join(f'--label "{l}"' for l in labels)
    cmd = (
        f'gh issue create --repo {GITHUB_REPO} '
        f'--title "{title}" '
        f'--body "{body}" '
        f'{labels_str}'
    )
    try:
        result = subprocess.check_output(cmd, shell=True, text=True, timeout=30)
        issue_url = result.strip()
        print(f"Issue created: {issue_url}")
        if "/issues/" in issue_url:
            return int(issue_url.split("/issues/")[1])
    except Exception as e:
        print(f"Failed to create issue: {e}")
    return None


def create_pr(branch: str, title: str, body: str, base: str = "main") -> Optional[str]:
    if not GITHUB_TOKEN:
        print(f"Cannot create PR: no GITHUB_TOKEN set (would create: {title})")
        return None
    cmd = (
        f'gh pr create --repo {GITHUB_REPO} '
        f'--base {base} '
        f'--head {branch} '
        f'--title "{title}" '
        f'--body "{body}" '
    )
    try:
        result = subprocess.check_output(cmd, shell=True, text=True, timeout=30)
        pr_url = result.strip()
        print(f"PR created: {pr_url}")
        return pr_url
    except Exception as e:
        print(f"Failed to create PR: {e}")
    return None


def detect_initiative_opportunities(goals: Dict[str, Any]) -> List[Dict[str, Any]]:
    initiatives: List[Dict[str, Any]] = []
    active_goals = [g for g in goals.get("primary_goals", []) if g.get("status") == "active"]
    high_priority = [g for g in active_goals if g.get("priority", 0) >= 8]
    ignored_goals = []
    for goal in high_priority:
        gid = goal.get("id", "")
        observations = [o for o in goals.get("observations", []) if o.get("goal_id") == gid]
        if not observations:
            ignored_goals.append(goal)
    for goal in ignored_goals:
        initiatives.append({
            "type": "stale_goal",
            "goal_id": goal.get("id", ""),
            "goal_name": goal.get("goal", "")[:80],
            "message": f"We haven't tracked progress on \"{goal.get('goal', '')[:60]}\" recently.",
        })
    return initiatives


def check_benchmark_plateau(benchmark_findings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    declining = [f for f in benchmark_findings if f.get("type") == "declining_trend"]
    if len(declining) >= 3:
        cats = [d["category"] for d in declining]
        return {
            "type": "plateau_warning",
            "categories": cats,
            "message": f"Multiple categories declining: {', '.join(cats)}. "
                       f"We keep adding capabilities but benchmark scores aren't improving.",
        }
    return None


def generate_daily_report() -> str:
    goals = load_goals()
    benchmark_findings = check_benchmark_health()
    goal_findings = check_goal_progress(goals)
    initiatives = detect_initiative_opportunities(goals)
    plateau = check_benchmark_plateau(benchmark_findings)
    body_parts = [f"## Daedalus Daily Engineering Report", f"**{datetime.now(timezone.utc).isoformat()}**", ""]

    if benchmark_findings:
        body_parts.append("### Benchmark Health")
        for f in benchmark_findings:
            body_parts.append(f"- \u26a0\ufe0f {f['message']}")
        body_parts.append("")

    if plateau:
        body_parts.append("### \U0001f6a8 Plateau Warning")
        body_parts.append(plateau["message"])
        body_parts.append(
            "I've noticed we've been adding capabilities but our benchmark scores "
            "aren't improving proportionally. Consider reviewing capability reuse "
            "and focusing on quality over quantity."
        )
        body_parts.append("")

    if initiatives:
        body_parts.append("### \U0001f4a1 Proactive Observations")
        for init in initiatives:
            body_parts.append(f"- {init['message']}")
        body_parts.append(f"- We should stop building new features until planning reliability exceeds 90%.")
        body_parts.append("")

    if goal_findings:
        body_parts.append("### Goal Tracking")
        for f in goal_findings:
            body_parts.append(f"- {f['message']}")
        body_parts.append("")

    body_parts.append("---")
    body_parts.append(DAEDALUS_SIGNATURE)
    return "\n".join(body_parts)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "report":
        report = generate_daily_report()
        print(report)
        if "--open-issue" in sys.argv:
            issue_num = create_issue(
                title=f"Daedalus Daily Report \u2014 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                body=report,
                labels=["daedalus", "daily-report"],
            )
            if issue_num:
                print(f"Daily report opened as issue #{issue_num}")
    elif mode == "check-goals":
        goals = load_goals()
        issues = check_goal_progress(goals)
        for i in issues:
            print(f"[{i['type']}] {i['message']}")
    elif mode == "detect-initiatives":
        goals = load_goals()
        initiatives = detect_initiative_opportunities(goals)
        for init in initiatives:
            print(f"[{init['type']}] {init['message']}")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: daedalus_actions.py [report|check-goals|detect-initiatives] [--open-issue]")


if __name__ == "__main__":
    main()
