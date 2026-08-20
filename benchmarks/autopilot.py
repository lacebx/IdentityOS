#!/usr/bin/env python3
"""Autonomous ratchet loop: Gemini proposes runtime fixes → ratchet judges.

Requires:
  Put GEMINI_API_KEY in benchmarks/.env (preferred) or export it.
  Optional: GEMINI_MODEL=gemini-3.6-flash

Examples:
  python benchmarks/autopilot.py --plan-only
  python benchmarks/autopilot.py --once
  python benchmarks/autopilot.py --loop --max-iters 5
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    # Prefer benchmarks/.env so root .env (other secrets) stays untouched.
    load_dotenv(ROOT / "benchmarks" / ".env")
except ImportError:
    pass

from benchmarks.autopilot_context import (  # noqa: E402
    build_coder_prompt,
    load_results,
    parse_recent_experiments,
)
from benchmarks.coder_gemini import CoderError, propose_edits  # noqa: E402
from benchmarks.invariants import ALLOWED_PREFIXES, ROOT as REPO_ROOT, classify_paths  # noqa: E402
from benchmarks.plateau import should_stop  # noqa: E402
from benchmarks.ratchet import next_exp_id  # noqa: E402

PROPOSALS_DIR = ROOT / "benchmarks" / "experiments" / "proposals"
DEFAULT_PYTEST = [
    "tests/test_user_profile_remember.py",
    "tests/test_ratchet.py",
    "tests/test_smollm_benchmark.py",
]


def _is_allowed_path(rel: str) -> bool:
    classified = classify_paths([rel])
    return bool(classified["allowed"])


def apply_edits(edits: list[dict[str, Any]]) -> list[str]:
    touched: list[str] = []
    # Validate all targets before mutating anything.
    for edit in edits:
        rel = str(edit.get("path") or "").strip()
        if not rel or not _is_allowed_path(rel):
            raise CoderError(f"edit path not allowlisted: {rel!r}")
        path = REPO_ROOT / rel
        if not path.exists():
            raise CoderError(
                f"edit target missing: {rel} "
                "(Gemini invented a path — prefer known files like adapters/openai_adapter.py / runtime/orchestrator.py)"
            )
        old = edit.get("search")
        new = edit.get("replace")
        if not isinstance(old, str) or not isinstance(new, str):
            raise CoderError(f"edit for {rel} needs string search/replace")
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise CoderError(f"edit for {rel}: search matched {count} times (need exactly 1)")

    for edit in edits:
        rel = str(edit.get("path") or "").strip()
        path = REPO_ROOT / rel
        old = edit["search"]
        new = edit["replace"]
        path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
        touched.append(rel)
    return touched


def run_pytest(targets: list[str]) -> None:
    cmd = [sys.executable, "-m", "pytest", *targets, "-q"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise CoderError(proc.stdout + proc.stderr or "pytest failed")


def run_ratchet(*, exp_id: str, hypothesis: str, change: str, pytest_targets: list[str]) -> int:
    cmd = [
        sys.executable,
        str(ROOT / "benchmarks" / "ratchet.py"),
        "--exp",
        exp_id,
        "--hypothesis",
        hypothesis,
        "--change",
        change,
    ]
    for target in pytest_targets:
        cmd.extend(["--pytest-target", target])
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    return proc.returncode


def save_proposal(exp_id: str, proposal: dict[str, Any]) -> Path:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROPOSALS_DIR / f"{exp_id}.json"
    path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    return path


def plan(*, model: str | None = None) -> dict[str, Any]:
    prompt = build_coder_prompt(
        results=load_results(),
        recent_experiments=parse_recent_experiments(),
    )
    return propose_edits(prompt, model=model)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gemini-powered ratchet autopilot")
    p.add_argument("--plan-only", action="store_true", help="Print Gemini JSON proposal; do not edit or benchmark")
    p.add_argument("--once", action="store_true", help="Plan → apply → pytest → ratchet once")
    p.add_argument("--loop", action="store_true", help="Repeat until plateau or --max-iters")
    p.add_argument("--max-iters", type=int, default=3)
    p.add_argument("--model", default=None, help="Gemini model id (default: GEMINI_MODEL env or gemini-2.0-flash)")
    p.add_argument("--dry-run", action="store_true", help="With --once, plan only and write proposal json")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.plan_only or args.once or args.loop):
        print("Pass --plan-only, --once, or --loop", file=sys.stderr)
        return 2

    iters = args.max_iters if args.loop else 1
    for iteration in range(iters):
        stop, reason = should_stop()
        if args.loop and stop:
            print(f"[autopilot] stopping: {reason}")
            return 0

        exp_id = next_exp_id()
        print(f"[autopilot] iteration {iteration + 1}/{iters} → {exp_id}")

        try:
            proposal = plan(model=args.model)
        except CoderError as exc:
            print(f"[autopilot] coder failed: {exc}", file=sys.stderr)
            return 1

        proposal_path = save_proposal(exp_id, proposal)
        print(f"[autopilot] proposal: {proposal_path}")

        if args.plan_only or args.dry_run:
            print(json.dumps(proposal, indent=2))
            if args.plan_only:
                return 0
            continue

        try:
            touched = apply_edits(proposal.get("edits") or [])
        except CoderError as exc:
            print(f"[autopilot] apply failed: {exc}", file=sys.stderr)
            return 1
        print(f"[autopilot] applied edits: {', '.join(touched)}")

        pytest_targets = proposal.get("tests_to_run") or DEFAULT_PYTEST
        try:
            run_pytest(pytest_targets)
        except CoderError as exc:
            print(f"[autopilot] pytest failed: {exc}", file=sys.stderr)
            return 1

        rc = run_ratchet(
            exp_id=exp_id,
            hypothesis=str(proposal.get("hypothesis") or ""),
            change=str(proposal.get("change") or ""),
            pytest_targets=pytest_targets,
        )
        if rc != 0:
            print(f"[autopilot] ratchet returned {rc} (REVERT or error)")
        else:
            print(f"[autopilot] KEEP {exp_id}")

        if not args.loop:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
