#!/usr/bin/env python3
"""
Daedalus Engineering Board — GitHub Projects v2 integration.

Creates and syncs Daedalus's engineering queue as a GitHub Project board.
Tracks active goals, in-progress work, needs-review items, and completed work.

Board columns:
  Investigating  — Problems Daedalus has detected but not yet analyzed
  In Progress    — Work Daedalus is actively doing
  Needs Review   — PRs or changes waiting for owner review
  Completed      — Finished items with evidence

Usage:
  python scripts/daedalus_board.py init     # Create the board (one-time)
  python scripts/daedalus_board.py sync     # Sync goals to board items
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

GITHUB_TOKEN = os.environ.get("DAEDALUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "lacebx/IdentityOS")
PROJECT_TITLE = "Daedalus Engineering Queue"


def run_gh(args: List[str], input_data: Optional[str] = None) -> str:
    cmd = ["gh"] + args + ["--repo", GITHUB_REPO]
    try:
        stdin = subprocess.PIPE if input_data else None
        result = subprocess.check_output(cmd, text=True, timeout=30, stdin=stdin)
        return result.strip()
    except subprocess.CalledProcessError as e:
        print(f"gh command failed: {' '.join(args)}: {e.output[:200]}")
        return ""
    except FileNotFoundError:
        print("gh CLI not available")
        return ""


def find_or_create_project() -> Optional[str]:
    result = run_gh(["project", "list", "--owner", GITHUB_REPO.split("/")[0], "--limit", "20"])
    if result:
        for line in result.split("\n"):
            if PROJECT_TITLE in line and "(" in line:
                return line.split("(")[-1].rstrip(")")
    number_str = input(f"Project '{PROJECT_TITLE}' not found. Create it? (y/N): ")
    if number_str.lower() == "y":
        result = run_gh([
            "project", "create", "--owner", GITHUB_REPO.split("/")[0],
            "--title", PROJECT_TITLE,
        ])
        if result:
            match = __import__("re").search(r"(\d+)", result)
            if match:
                return match.group(1)
    return None


def add_item_to_project(project_id: str, title: str, body: str, status: str = "Todo") -> bool:
    result = run_gh([
        "project", "item-add", project_id,
        "--title", title,
        "--body", body,
    ])
    return bool(result)


def sync_goals_to_board() -> None:
    goals_path = Path(".daedalus/goals.json")
    if not goals_path.exists():
        print("No goals.json found")
        return
    goals = json.loads(goals_path.read_text())
    project_id = find_or_create_project()
    if not project_id:
        print("Could not find or create project")
        return
    for g in goals.get("primary_goals", []):
        status = g.get("status", "active")
        priority = g.get("priority", 0)
        name = g.get("goal", "")[:80]
        if status == "active":
            if priority >= 9:
                board_status = "In Progress"
            else:
                board_status = "Investigating"
        elif status == "completed":
            board_status = "Completed"
        elif status == "deferred":
            continue
        else:
            board_status = "Needs Review"
        evidence = g.get("evidence", [])
        body = f"Priority: {priority}/10\nStatus: {status}\n"
        if evidence:
            body += f"\nEvidence:\n" + "\n".join(f"- {e}" for e in evidence)
        add_item_to_project(project_id, name, body, board_status)
    print(f"Board synced: {PROJECT_TITLE}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if mode == "init":
        project_id = find_or_create_project()
        if project_id:
            print(f"Project ready: {PROJECT_TITLE} (ID: {project_id})")
        else:
            print("Create the project manually at: https://github.com/{GITHUB_REPO}/projects")
    elif mode == "sync":
        sync_goals_to_board()
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
