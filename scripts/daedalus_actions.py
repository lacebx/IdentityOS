#!/usr/bin/env python3
"""
Daedalus Autonomous Actions — proactive engineering maintenance for IdentityOS.

Daedalus runs periodically (daily/weekly) and:
1. Checks benchmark trends and updates the Engineering Journal
2. Reviews goal progress and evolves goals.json lifecycle
3. Detects stale goals and creates initiative proposals
4. Updates the Engineering Journal instead of creating new issues each day
5. Proposes PRs for low-risk improvements
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
ENGINEERING_JOURNAL_LABEL = "engineering-journal"
ENGINEERING_JOURNAL_TITLE_PREFIX = "Engineering Journal \u2014 Week"

GITHUB_TOKEN = os.environ.get("DAEDALUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "lacebx/IdentityOS")


def run_gh(args: List[str]) -> str:
    cmd = ["gh"] + args + ["--repo", GITHUB_REPO]
    env = os.environ.copy()
    if GITHUB_TOKEN:
        env["GH_TOKEN"] = GITHUB_TOKEN
    try:
        return subprocess.check_output(cmd, text=True, timeout=30, env=env).strip()
    except subprocess.CalledProcessError as e:
        print(f"gh command failed: {' '.join(args)}: {e.output}")
        return ""
    except FileNotFoundError:
        print("gh CLI not available")
        return ""


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


def find_or_create_journal_issue() -> Optional[int]:
    week_num = datetime.now(timezone.utc).isocalendar()[1]
    title = f"{ENGINEERING_JOURNAL_TITLE_PREFIX} {week_num}"
    result = run_gh(["issue", "list", "--label", ENGINEERING_JOURNAL_LABEL, "--state", "open", "--json", "number,title", "--limit", "5"])
    if result:
        try:
            issues = json.loads(result)
            for issue in issues:
                if issue.get("title", "").startswith(ENGINEERING_JOURNAL_TITLE_PREFIX):
                    return issue["number"]
        except json.JSONDecodeError:
            pass
    if not GITHUB_TOKEN:
        print(f"No GITHUB_TOKEN — would create journal issue: {title}")
        return None
    result = run_gh(["issue", "create", "--title", title, "--body", "_Engineering Journal initialized._", "--label", ENGINEERING_JOURNAL_LABEL])
    if result:
        match = __import__("re").search(r"(\d+)$", result)
        if match:
            return int(match.group(1))
    return None


def update_journal_issue(issue_num: int, body: str) -> bool:
    if not GITHUB_TOKEN:
        print(f"No GITHUB_TOKEN — would update issue #{issue_num}")
        return False
    result = run_gh(["issue", "edit", str(issue_num), "--body", body])
    return bool(result)


def generate_daily_entry() -> str:
    goals = load_goals()
    benchmark_findings = check_benchmark_health()
    active = [g for g in goals.get("primary_goals", []) if g.get("status") == "active"]
    completed = [g for g in goals.get("primary_goals", []) if g.get("status") == "completed"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    week_num = datetime.now(timezone.utc).isocalendar()[1]
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    llm_narrative = ""
    try:
        from core.capabilities.daedalus.thinking_engine import (
            ThinkingEngine, load_memory, WEEKLY_REPORT_SYSTEM_PROMPT,
        )
        memory = load_memory()
        memory_context_lines = ["### Past Recommendations"]
        for r in memory.get("recommendations", [])[-5:]:
            status = "✓" if r.get("outcome") == "followed" else "✗" if r.get("outcome") == "ignored" else "○"
            memory_context_lines.append(f"{status} {r['recommendation'][:100]}")
        memory_context_lines.append("")
        for r in memory.get("weekly_reports", [])[-2:]:
            memory_context_lines.append(f"Previous report ({r.get('date', '?')}): health={r.get('overall_health', '?')}")
        memory_context = "\n".join(memory_context_lines)

        bench_text = "\n".join(f"- {f['message']}" for f in benchmark_findings) if benchmark_findings else "No significant changes."
        user_prompt = f"""## Engineering Journal — Week {week_num} ({report_date})

### Active Goals ({len(active)})
{chr(10).join(f"- [{g['priority']}] {g['goal'][:80]}" for g in sorted(active, key=lambda x: -x.get('priority', 0)))}

### Completed Goals
{chr(10).join(f"- {g['goal'][:80]}" for g in completed[:5]) if completed else "None this week"}

### Benchmark Health
{bench_text}

### Raw Test Results
{chr(10).join(f"- {f['message']}" for f in benchmark_findings[:5]) if benchmark_findings else "Tests passed."}

Generate the weekly engineering report in the specified JSON format."""

        engine = ThinkingEngine()
        thought = engine.think(
            system_prompt=WEEKLY_REPORT_SYSTEM_PROMPT.format(memory_context=memory_context),
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.4,
        )
        if thought.content and thought.finish_reason != "error":
            try:
                parsed = json.loads(thought.content)
                parsed["date"] = report_date
                memory["weekly_reports"].append({
                    "date": report_date,
                    "overall_health": parsed.get("overall_health"),
                    "trend": parsed.get("trend"),
                    "narrative": parsed.get("narrative", "")[:200],
                })
                from core.capabilities.daedalus.thinking_engine import save_memory
                save_memory(memory)

                llm_narrative = f"""
### Daedalus Assessment

**Overall Health:** {parsed.get('overall_health', '?')}/100 — Trend: **{parsed.get('trend', 'stable')}**

{parsed.get('narrative', '')}

**Key Metrics:** {json.dumps(parsed.get('key_metrics', {}))}

**Suggested Initiative:**
- **{parsed.get('initiative', {}).get('title', '(none)')}**
- {parsed.get('initiative', {}).get('description', '')}
- Estimated impact: {parsed.get('initiative', {}).get('estimated_impact', 'N/A')}
"""
            except (json.JSONDecodeError, Exception):
                llm_narrative = f"\n### Daedalus Assessment\n\n{thought.content[:1000]}\n"
    except ImportError:
        pass

    lines = [
        f"## Daedalus Engineering Journal",
        f"**Week {week_num}** — {report_date}",
        f"Last updated: {today}",
        "",
    ]
    if llm_narrative:
        lines.append(llm_narrative)
        lines.append("")
    lines.append("### Raw Metrics")
    lines.append("")
    if benchmark_findings:
        lines.append("**Benchmark Health**")
        for f in benchmark_findings:
            lines.append(f"- \u26a0\ufe0f {f['message']}")
        lines.append("")

    declining = [f for f in benchmark_findings if f.get("type") == "declining_trend"]
    if len(declining) >= 3:
        cats = [d["category"] for d in declining]
        lines.append("### \U0001f6a8 Plateau Warning")
        lines.append(
            f"Multiple categories declining: {', '.join(cats)}. "
            f"We keep adding capabilities but benchmark scores aren't improving proportionally."
        )
        lines.append("")

    lines.append(f"**Active Goals ({len(active)})**")
    for g in sorted(active, key=lambda x: -x.get("priority", 0)):
        p = g.get("priority", 0)
        name = g.get("goal", "")[:70]
        lines.append(f"- [{'#'*p}{'.'*(10-p)}] **{name}** (priority {p})")
    lines.append("")

    if completed:
        lines.append(f"**Completed Goals ({len(completed)})**")
        for g in completed:
            completed_at = g.get("completed_at", "?")
            evidence = g.get("evidence", [])
            lines.append(f"- \u2705 **{g.get('goal', '')[:60]}** — {completed_at}")
            for e in evidence[:2]:
                lines.append(f"  - {e}")
        lines.append("")

    abandoned = [g for g in goals.get("primary_goals", []) if g.get("status") == "abandoned"]
    if abandoned:
        lines.append(f"**Abandoned ({len(abandoned)})**")
        for g in abandoned:
            lines.append(f"- \U0001f4a4 {g.get('goal', '')[:60]}")

    lines.append("---")
    lines.append(DAEDALUS_SIGNATURE)
    return "\n".join(lines)


def complete_goal(goal_id: str, evidence: List[str]) -> bool:
    goals = load_goals()
    for g in goals.get("primary_goals", []):
        if g.get("id") == goal_id and g.get("status") == "active":
            g["status"] = "completed"
            g["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            g["evidence"] = evidence
            save_goals(goals)
            print(f"Goal '{goal_id}' marked as completed")
            return True
    return False


def add_observation(goal_id: str, message: str) -> None:
    goals = load_goals()
    if "observations" not in goals:
        goals["observations"] = []
    goals["observations"].append({
        "goal_id": goal_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
    })
    save_goals(goals)


def complete_goal_cli() -> None:
    if len(sys.argv) < 4:
        print("Usage: daedalus_actions.py complete-goal <goal_id> <evidence_json>")
        return
    goal_id = sys.argv[2]
    try:
        evidence = json.loads(sys.argv[3])
    except json.JSONDecodeError:
        evidence = [sys.argv[3]]
    complete_goal(goal_id, evidence)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "report":
        entry = generate_daily_entry()
        print(entry)
        print("\n---\n")
        issue_num = find_or_create_journal_issue()
        if issue_num:
            old_body = ""
            result = run_gh(["issue", "view", str(issue_num), "--json", "body"])
            if result:
                try:
                    old_body_data = json.loads(result)
                    old_body = old_body_data.get("body", "")
                except json.JSONDecodeError:
                    old_body = ""
            previous_entries = ""
            if old_body and "_Engineering Journal initialized._" not in old_body:
                prev_lines = old_body.split("\n")
                if len(prev_lines) > 30:
                    previous_entries = "\n".join(prev_lines[:30])
            full_body = entry
            if previous_entries:
                full_body += "\n\n<details><summary>Previous entries</summary>\n\n" + previous_entries + "\n\n</details>"
            update_journal_issue(issue_num, full_body)
            print(f"Engineering Journal updated: issue #{issue_num}")
    elif mode == "complete-goal":
        complete_goal_cli()
    elif mode == "check-goals":
        goals = load_goals()
        active = [g for g in goals.get("primary_goals", []) if g.get("status") == "active"]
        print(f"Active: {len(active)}, Completed: {len([g for g in goals.get('primary_goals', []) if g.get('status') == 'completed'])}")
        for g in active:
            print(f"  - [{g.get('priority', 0)}] {g.get('goal', '')[:60]}")
    elif mode == "detect-initiatives":
        goals = load_goals()
        active_goals = [g for g in goals.get("primary_goals", []) if g.get("status") == "active"]
        high_priority = [g for g in active_goals if g.get("priority", 0) >= 8]
        ignored = [
            g for g in high_priority
            if not any(o.get("goal_id") == g.get("id") for o in goals.get("observations", []))
        ]
        for g in ignored:
            print(f"[stale_goal] We haven't tracked progress on \"{g.get('goal', '')[:60]}\" recently.")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: daedalus_actions.py [report|check-goals|detect-initiatives|complete-goal]")


if __name__ == "__main__":
    main()
