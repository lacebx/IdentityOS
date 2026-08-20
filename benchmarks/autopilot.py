#!/usr/bin/env python3
"""Autonomous ratchet loop: LLM proposes runtime fixes → ratchet judges.

Coder providers (default order): gemini → groq → deepseek
Override with --provider or AUTOPILOT_CODER_ORDER in benchmarks/.env.

Examples:
  python benchmarks/autopilot.py --plan-only --provider deepseek
  python benchmarks/autopilot.py --once --provider deepseek
  python benchmarks/autopilot.py --once --reuse-latest
  python benchmarks/autopilot.py --once --from-proposal benchmarks/experiments/proposals/EXP-011.json
  python benchmarks/autopilot.py --loop --max-iters 5 --provider deepseek
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

    load_dotenv(ROOT / "benchmarks" / ".env")
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from benchmarks.autopilot_context import (  # noqa: E402
    build_coder_prompt,
    load_results,
    parse_recent_experiments,
)
from benchmarks.coder_llm import CoderError, propose_edits  # noqa: E402
from benchmarks.invariants import ROOT as REPO_ROOT, classify_paths  # noqa: E402
from benchmarks.plateau import should_stop  # noqa: E402
from benchmarks.ratchet import next_exp_id  # noqa: E402

PROPOSALS_DIR = ROOT / "benchmarks" / "experiments" / "proposals"
DEFAULT_PYTEST = [
    "tests/test_user_profile_remember.py",
    "tests/test_ratchet.py",
    "tests/test_smollm_benchmark.py",
]


def _is_allowed_path(rel: str) -> bool:
    return bool(classify_paths([rel])["allowed"])


def apply_edits(edits: list[dict[str, Any]]) -> list[str]:
    touched: list[str] = []
    for edit in edits:
        rel = str(edit.get("path") or "").strip()
        if not rel or not _is_allowed_path(rel):
            raise CoderError(f"edit path not allowlisted: {rel!r}")
        path = REPO_ROOT / rel
        if not path.exists():
            raise CoderError(f"edit target missing: {rel}")
        old, new = edit.get("search"), edit.get("replace")
        if not isinstance(old, str) or not isinstance(new, str):
            raise CoderError(f"edit for {rel} needs string search/replace")
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise CoderError(f"edit for {rel}: search matched {count} times (need exactly 1)")
    for edit in edits:
        rel = str(edit["path"]).strip()
        path = REPO_ROOT / rel
        path.write_text(
            path.read_text(encoding="utf-8").replace(edit["search"], edit["replace"], 1),
            encoding="utf-8",
        )
        touched.append(rel)
    return touched


def run_pytest(targets: list[str]) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
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
    return subprocess.run(cmd, cwd=ROOT, text=True).returncode


def save_proposal(exp_id: str, proposal: dict[str, Any]) -> Path:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROPOSALS_DIR / f"{exp_id}.json"
    path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    return path


def latest_proposal_path() -> Path | None:
    if not PROPOSALS_DIR.exists():
        return None
    paths = sorted(PROPOSALS_DIR.glob("EXP-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def plan(*, model: str | None = None, provider: str | None = None) -> dict[str, Any]:
    # Compact prompts keep Groq free-tier TPM under ~8k.
    prompt = build_coder_prompt(
        results=load_results(),
        recent_experiments=parse_recent_experiments(),
        compact=True,
    )
    return propose_edits(prompt, model=model, provider=provider)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multi-provider ratchet autopilot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Providers: gemini | groq | deepseek\n"
            "Models via env: GEMINI_MODEL, GROQ_CODER_MODEL, DEEPSEEK_CODER_MODEL\n"
            "  deepseek default: deepseek-v4-flash  (pro: deepseek-v4-pro)\n"
            "  groq default: openai/gpt-oss-20b\n"
            "  gemini default: gemini-3.6-flash\n"
            "Overnight tip: --provider deepseek  OR  AUTOPILOT_CODER_ORDER=deepseek,groq,gemini"
        ),
    )
    p.add_argument("--plan-only", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--max-iters", type=int, default=3)
    p.add_argument(
        "--model",
        default=None,
        help="Override model for --provider (e.g. deepseek-v4-flash or deepseek-v4-pro)",
    )
    p.add_argument(
        "--provider",
        choices=("gemini", "groq", "deepseek"),
        default=None,
        help="Force one coder (recommended for overnight: deepseek)",
    )
    p.add_argument("--from-proposal", type=Path)
    p.add_argument("--reuse-latest", action="store_true", help="Use newest proposals/EXP-*.json (no API)")
    p.add_argument("--dry-run", action="store_true")
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

        if args.from_proposal:
            proposal = json.loads(Path(args.from_proposal).read_text(encoding="utf-8"))
            print(f"[autopilot] using proposal file: {args.from_proposal}")
        elif args.reuse_latest:
            latest = latest_proposal_path()
            if latest is None:
                print("[autopilot] no proposals/EXP-*.json found", file=sys.stderr)
                return 1
            proposal = json.loads(latest.read_text(encoding="utf-8"))
            print(f"[autopilot] reusing latest proposal: {latest}")
        else:
            try:
                proposal = plan(model=args.model, provider=args.provider)
                print(f"[autopilot] coder provider: {proposal.pop('_coder_provider', args.provider or 'auto')}")
                print(f"[autopilot] proposal: {save_proposal(exp_id, proposal)}")
            except CoderError as exc:
                latest = latest_proposal_path()
                if args.once and latest is not None:
                    print(f"[autopilot] coder failed ({exc}); falling back to {latest}", file=sys.stderr)
                    proposal = json.loads(latest.read_text(encoding="utf-8"))
                else:
                    print(f"[autopilot] coder failed: {exc}", file=sys.stderr)
                    return 1

        if args.plan_only or args.dry_run:
            print(json.dumps(proposal, indent=2))
            return 0 if args.plan_only else 0

        edits = proposal.get("edits") or []
        if not edits:
            print("[autopilot] empty edits — refuse ratchet", file=sys.stderr)
            return 2

        try:
            print(f"[autopilot] applied edits: {', '.join(apply_edits(edits))}")
            targets = proposal.get("tests_to_run") or DEFAULT_PYTEST
            run_pytest(targets)
        except CoderError as exc:
            print(f"[autopilot] apply/pytest failed: {exc}", file=sys.stderr)
            return 1

        rc = run_ratchet(
            exp_id=exp_id,
            hypothesis=str(proposal.get("hypothesis") or ""),
            change=str(proposal.get("change") or ""),
            pytest_targets=proposal.get("tests_to_run") or DEFAULT_PYTEST,
        )
        print(f"[autopilot] {'KEEP' if rc == 0 else f'returned {rc}'} {exp_id}")
        if not args.loop:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
