#!/usr/bin/env python3
"""Open one consolidated PR after N successful ratchet KEEP commits.

Working branch ``ratchet/smollm-v0.1`` accumulates KEEP commits linearly.
When you have enough wins, this script updates a clearly named integration
branch and opens a single PR to ``main`` — so you do not end up with dozens
of orphan experiment branches.

    python benchmarks/ratchet_pr.py --status
    python benchmarks/ratchet_pr.py --min-keeps 5
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_BRANCH = "ratchet/smollm-v0.1"
CONSOLIDATED_BRANCH = "ratchet/smollm-consolidated-v0.1"
KEEP_RE = re.compile(r"^ratchet KEEP EXP-\d+", re.MULTILINE)


class RatchetPrError(RuntimeError):
    pass


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def git_out(args: list[str]) -> str:
    proc = _git(args, check=False)
    if proc.returncode != 0:
        raise RatchetPrError(proc.stderr.strip() or proc.stdout.strip() or "git failed")
    return (proc.stdout or "").strip()


def list_keep_commits(limit: int = 50) -> list[dict[str, str]]:
    raw = git_out(["log", f"-{limit}", "--pretty=format:%H%x09%s"])
    keeps: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, subject = line.split("\t", 1)
        if subject.startswith("ratchet KEEP"):
            keeps.append({"sha": sha, "subject": subject})
    return keeps


def render_pr_body(keeps: list[dict[str, str]], bare_rate: str, idos_rate: str) -> str:
    lines = [
        "## Summary",
        "",
        f"Consolidates **{len(keeps)}** measured runtime improvements on the frozen "
        "SmolLM2-360M benchmark (v0.1.0).",
        "",
        f"- Model: `smollm2:360m-instruct-q4_0`",
        f"- Bare baseline: {bare_rate}",
        f"- Latest IDOS: {idos_rate}",
        "",
        "Each commit passed the ratchet gates (full suite, same model, success up, "
        "hallucination not worse, latency budget, category floors, pytest green).",
        "",
        "## KEEP commits",
        "",
    ]
    for entry in keeps:
        lines.append(f"- `{entry['sha'][:10]}` {entry['subject']}")
    lines.extend(
        [
            "",
            "## Test plan",
            "",
            "- [ ] `python -m pytest tests/test_ratchet.py tests/test_smollm_benchmark.py tests/test_adapters.py`",
            "- [ ] `python benchmarks/runner.py --report-only`",
            "- [ ] Spot-check `benchmarks/experiments/EXP-*.md`",
            "",
        ]
    )
    return "\n".join(lines)


def read_success_rate(path: Path) -> str:
    if not path.exists():
        return "not frozen"
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}
    if summary.get("n"):
        rate = float(summary.get("success_rate") or 0) * 100
        return f"{rate:.0f}% ({summary.get('success')}/{summary.get('n')})"
    tasks = data.get("tasks") or []
    if not tasks:
        return "not frozen"
    success = sum(1 for t in tasks if t.get("success"))
    return f"{success * 100 // len(tasks)}% ({success}/{len(tasks)})"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Consolidated ratchet PR helper")
    p.add_argument("--min-keeps", type=int, default=5, help="KEEP commits required before opening a PR")
    p.add_argument("--work-branch", default=WORK_BRANCH)
    p.add_argument("--consolidated-branch", default=CONSOLIDATED_BRANCH)
    p.add_argument("--base", default="main")
    p.add_argument("--status", action="store_true", help="Print KEEP progress and exit")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    keeps = list_keep_commits()
    current = git_out(["rev-parse", "--abbrev-ref", "HEAD"])

    if args.status:
        print(f"branch: {current}")
        print(f"KEEP commits: {len(keeps)} / {args.min_keeps} required for consolidated PR")
        for entry in keeps:
            print(f"  {entry['sha'][:10]}  {entry['subject']}")
        return 0

    if len(keeps) < args.min_keeps:
        raise RatchetPrError(
            f"only {len(keeps)} KEEP commit(s); need {args.min_keeps}. "
            f"Run `python benchmarks/ratchet_pr.py --status` to inspect."
        )

    if current != args.work_branch:
        print(f"warning: on {current}, expected {args.work_branch}", file=sys.stderr)

    head = git_out(["rev-parse", "HEAD"])
    bare_rate = read_success_rate(ROOT / "benchmarks/baseline/results.json")
    idos_rate = read_success_rate(ROOT / "benchmarks/idos/results.json")
    body = render_pr_body(keeps, bare_rate, idos_rate)
    title = f"Ratchet: {len(keeps)} SmolLM2 runtime wins (v0.1.0 benchmark)"

    if args.dry_run:
        print(f"would push {args.consolidated_branch} -> {head[:10]}")
        print(f"would open PR: {title}")
        print(body)
        return 0

    _git(["branch", "-f", args.consolidated_branch, head], check=True)
    push = _git(["push", "-u", "origin", args.consolidated_branch, "--force-with-lease"], check=False)
    if push.returncode != 0:
        push = _git(["push", "-u", "origin", args.consolidated_branch], check=False)
    if push.returncode != 0:
        raise RatchetPrError(push.stderr.strip() or "git push failed")

    existing = subprocess.run(
        ["gh", "pr", "list", "--head", f"origin:{args.consolidated_branch}", "--json", "url", "--jq", ".[0].url"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if existing.returncode == 0 and (existing.stdout or "").strip():
        url = existing.stdout.strip()
        print(f"PR already open: {url}")
        return 0

    create = subprocess.run(
        ["gh", "pr", "create", "--base", args.base, "--head", args.consolidated_branch, "--title", title, "--body", body],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if create.returncode != 0:
        raise RatchetPrError(create.stderr.strip() or create.stdout.strip() or "gh pr create failed")
    print((create.stdout or "").strip())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RatchetPrError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
