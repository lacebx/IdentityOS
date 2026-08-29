#!/usr/bin/env python3
"""IDOS capability ratchet — Karpathy-style keep/revert on a frozen eval.

    python benchmarks/ratchet.py --bootstrap --hypothesis "First IDOS baseline"
    python benchmarks/ratchet.py --exp EXP-001 --hypothesis "Wire Ollama tool calls"

The model and the task suite do not move. Only the runtime may change.
KEEP commits onto the current branch (refuses main/master). REVERT restores
allowlisted runtime files to HEAD and keeps the experiment log.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.decision import Decision, decide  # noqa: E402
from benchmarks.invariants import (  # noqa: E402
    ALLOWED_PREFIXES,
    check_lock,
    classify_paths,
    collect_harness_files,
    experiment_locked_violations,
    load_lock,
    write_lock,
)
from benchmarks.runner import (  # noqa: E402
    DEFAULT_HOST,
    DEFAULT_MODEL,
    IDOS_DIR,
    TASKS_PATH,
    copy_frozen,
    load_suite,
    run_mode,
    select_tasks,
    write_reports,
)

EXPERIMENTS_DIR = ROOT / "benchmarks" / "experiments"
PROTECTED_BRANCHES = {"main", "master"}
HACK_PATTERNS = (
    re.compile(r"if\s+[\"'].*837\s*\*\s*492", re.I),
    re.compile(r"if\s+[\"'].*2\s*\+\s*2", re.I),
    re.compile(r"if\s+[\"']What is my project", re.I),
    re.compile(r"IdentityOS\. Its purpose is persistent", re.I),
)
DEFAULT_PYTEST = [
    "tests/test_smollm_benchmark.py",
    "tests/test_ratchet.py",
    "tests/test_adapters.py",
    "tests/test_chat_commands.py",
]


class RatchetError(RuntimeError):
    pass


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def git_text(args: list[str]) -> str:
    proc = _git(args, check=False)
    if proc.returncode != 0:
        raise RatchetError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return (proc.stdout or "").strip()


def current_branch() -> str:
    return git_text(["rev-parse", "--abbrev-ref", "HEAD"])


def current_sha() -> str:
    return git_text(["rev-parse", "HEAD"])


def changed_files_vs(sha: str) -> list[str]:
    named = git_text(["diff", "--name-only", sha])
    untracked = git_text(["ls-files", "--others", "--exclude-standard"])
    files = [line for line in named.splitlines() if line] + [line for line in untracked.splitlines() if line]
    return sorted(set(files))


def next_exp_id() -> str:
    highest = 0
    if EXPERIMENTS_DIR.exists():
        for path in EXPERIMENTS_DIR.glob("EXP-*.md"):
            stem = path.stem
            if stem == "TEMPLATE":
                continue
            try:
                highest = max(highest, int(stem.split("-", 1)[1]))
            except (IndexError, ValueError):
                continue
    return f"EXP-{highest + 1:03d}"


def load_results(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def scan_diff_for_hacks(diff: str) -> list[str]:
    hits: list[str] = []
    for pattern in HACK_PATTERNS:
        if pattern.search(diff):
            hits.append(pattern.pattern)
    return hits


def render_experiment(
    *,
    exp_id: str,
    verdict: str,
    hypothesis: str,
    change: str,
    decision: Decision,
    model: str,
    suite: str,
    pytest_ok: bool | None,
    run_dir: str | None,
) -> str:
    def cell(stats: dict[str, Any], key: str) -> str:
        if not stats or stats.get("n") in (None, 0):
            return "—"
        if key == "latency":
            lat = stats.get("avg_latency_s")
            return "—" if lat is None else f"{lat}s"
        if key == "success":
            return f"{stats.get('success_rate', 0) * 100:.0f}% ({stats.get('success')}/{stats.get('n')})"
        if key == "hallucination":
            return f"{stats.get('hallucination_rate', 0) * 100:.0f}% ({stats.get('hallucination')}/{stats.get('n')})"
        cats = stats.get("categories") or {}
        bucket = cats.get(key)
        if not bucket:
            return "—"
        return f"{bucket.get('success_rate', 0) * 100:.0f}% ({bucket.get('success')}/{bucket.get('n')})"

    before, after = decision.before, decision.after
    reasons = "\n".join(f"- {r}" for r in decision.reasons) or "- (none)"
    failures = []
    # after blob isn't on Decision; reasons cover it
    return (
        f"# {exp_id}\n\n"
        f"Status: {verdict}\n"
        f"Date: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"## Hypothesis\n\n{hypothesis.strip() or '(not provided)'}\n\n"
        f"## Change\n\n{change.strip() or '(not provided)'}\n\n"
        f"## Benchmark\n\n"
        f"- Suite: {suite}\n"
        f"- Model: `{model}`\n"
        f"- Pytest: {'passed' if pytest_ok else 'skipped' if pytest_ok is None else 'failed'}\n"
        f"- Run dir: `{run_dir or 'n/a'}`\n\n"
        f"## Result\n\n"
        f"| Metric | Before | After |\n"
        f"|---|---|---|\n"
        f"| Task Success | {cell(before, 'success')} | {cell(after, 'success')} |\n"
        f"| Hallucination | {cell(before, 'hallucination')} | {cell(after, 'hallucination')} |\n"
        f"| Memory | {cell(before, 'memory')} | {cell(after, 'memory')} |\n"
        f"| Tools | {cell(before, 'tools')} | {cell(after, 'tools')} |\n"
        f"| Persistence | {cell(before, 'persistence')} | {cell(after, 'persistence')} |\n"
        f"| Long tasks | {cell(before, 'long_task')} | {cell(after, 'long_task')} |\n"
        f"| Truthfulness | {cell(before, 'truthfulness')} | {cell(after, 'truthfulness')} |\n"
        f"| Avg Latency | {cell(before, 'latency')} | {cell(after, 'latency')} |\n\n"
        f"## Gates\n\n"
        + "\n".join(f"- `{k}`: {'pass' if v else 'FAIL'}" for k, v in decision.gates.items())
        + "\n\n## Reasons\n\n"
        + reasons
        + "\n\n## Decision\n\n"
        + f"{verdict}\n"
    )


def run_pytest(targets: list[str]) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q", "--tb=line"],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RatchetError(f"pytest failed (exit {proc.returncode})")


def freeze_idos(run_dir: Path, *, force: bool) -> None:
    copy_frozen(run_dir, IDOS_DIR, "idos baseline", force=force)


def restore_allowlisted(start_sha: str) -> list[str]:
    """Restore allowlisted tracked files to *start_sha*. Leave other dirty files alone."""
    changed = changed_files_vs(start_sha)
    classified = classify_paths(changed)
    restored: list[str] = []
    tracked = set(git_text(["ls-files"]).splitlines())
    for rel in classified["allowed"]:
        path = ROOT / rel
        if rel in tracked:
            _git(["restore", "--source", start_sha, "--worktree", "--staged", "--", rel], check=True)
            restored.append(rel)
        elif path.exists() and path.is_file():
            path.unlink()
            restored.append(rel)
    return restored


def commit_keep(*, exp_id: str, decision: Decision, files: list[str], hypothesis: str) -> None:
    if not files:
        raise RatchetError("KEEP but no files to commit")
    _git(["add", "--", *files], check=True)
    before_s = decision.before.get("success_rate")
    after_s = decision.after.get("success_rate")
    msg = (
        f"ratchet KEEP {exp_id}: "
        f"{(before_s or 0) * 100:.0f}% → {(after_s or 0) * 100:.0f}%\n\n"
        f"{hypothesis.strip()}\n\n"
        + "\n".join(decision.reasons)
        + "\n"
    )
    proc = subprocess.run(
        ["git", "commit", "-F", "-"],
        cwd=ROOT,
        text=True,
        input=msg,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RatchetError(proc.stderr.strip() or proc.stdout.strip() or "git commit failed")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IDOS keep/revert ratchet on the frozen SmolLM2 suite")
    p.add_argument("--exp", help="Experiment id (default: next EXP-NNN)")
    p.add_argument("--hypothesis", default="", help="Why this runtime change should raise the score")
    p.add_argument("--change", default="", help="What subsystem changed")
    p.add_argument("--bootstrap", action="store_true", help="Freeze the first IDOS baseline (no previous score)")
    p.add_argument("--decide-only", action="store_true", help="Judge two result files; do not run the model")
    p.add_argument("--before", type=Path, help="Previous IDOS results.json")
    p.add_argument("--after", type=Path, help="Candidate IDOS results.json")
    p.add_argument("--write-lock", action="store_true", help="Rewrite ratchet.lock.json from the current frozen files")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--skip-bench", action="store_true", help="Do not call Ollama; requires --after")
    p.add_argument("--full-tests", action="store_true", help="Run the entire tests/ tree")
    p.add_argument("--pytest-target", action="append", dest="pytest_targets")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--no-revert", action="store_true", help="On REVERT, do not restore files")
    p.add_argument("--push", action="store_true", help="git push -u origin HEAD after KEEP")
    p.add_argument("--allow-main", action="store_true")
    p.add_argument("--reset-identity", action="store_true", default=True)
    p.add_argument("--keep-identity", action="store_true", help="Do not wipe the benchmark identity")
    p.add_argument("--latency-budget", type=float, default=1.25)
    p.add_argument("--max-category-drop", type=int, default=1)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--model", default=DEFAULT_MODEL)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.write_lock:
        lock = write_lock()
        print(json.dumps(lock, indent=2))
        return 0

    lock = load_lock()
    invariant_errors = check_lock(lock)
    if invariant_errors:
        for err in invariant_errors:
            print(f"error: {err}", file=sys.stderr)
        return 2

    exp_id = args.exp or next_exp_id()
    expected_n = int(lock.get("suite_n") or 30)
    expected_model = str(lock.get("model") or DEFAULT_MODEL)
    if args.model != expected_model:
        raise RatchetError(f"model {args.model!r} != locked {expected_model!r}")

    start_sha = current_sha()
    branch = current_branch()

    if args.decide_only:
        before = load_results(args.before or (IDOS_DIR / "results.json"))
        after = load_results(args.after) if args.after else None
        if after is None:
            raise RatchetError("--decide-only requires --after")
        decision = decide(
            before=before,
            after=after,
            expected_n=expected_n,
            expected_model=expected_model,
            latency_budget=args.latency_budget,
            max_category_drop=args.max_category_drop,
            bootstrap=args.bootstrap,
        )
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.keep else 1

    if branch in PROTECTED_BRANCHES and not args.allow_main and not args.no_commit:
        raise RatchetError(
            f"refusing to KEEP-commit on {branch}. Switch to ratchet/smollm-v0.1 "
            "(or pass --allow-main / --no-commit)."
        )

    changed = changed_files_vs(start_sha)
    classified = classify_paths(changed)
    tracked = set(git_text(["ls-files"]).splitlines())
    locked_violations = experiment_locked_violations(changed, tracked, lock)
    if locked_violations:
        raise RatchetError(
            "locked eval/harness files changed; aborting before the loop can cheat:\n  "
            + "\n  ".join(locked_violations)
        )
    if classified["other"]:
        print("warning: files outside the runtime allowlist will not be committed or reverted:", file=sys.stderr)
        for rel in classified["other"]:
            print(f"  {rel}", file=sys.stderr)

    diff = git_text(["diff", start_sha, "--", *ALLOWED_PREFIXES]) if changed else ""
    hacks = scan_diff_for_hacks(diff)
    if hacks:
        raise RatchetError("diff looks like a benchmark-specific hack:\n  " + "\n  ".join(hacks))

    pytest_ok: bool | None = None
    if args.skip_tests:
        pytest_ok = None
    else:
        targets = ["tests/"] if args.full_tests else (args.pytest_targets or DEFAULT_PYTEST)
        run_pytest(targets)
        pytest_ok = True

    suite = load_suite(TASKS_PATH)
    run_dir: Path | None = None
    after: dict[str, Any] | None
    if args.skip_bench:
        if not args.after:
            raise RatchetError("--skip-bench requires --after")
        after = load_results(args.after)
    else:
        tasks = select_tasks(suite, None, None, None)
        if len(tasks) != expected_n:
            raise RatchetError(f"suite has {len(tasks)} tasks, lock expects {expected_n}")
        try:
            run_dir = run_mode(
                mode="idos",
                suite=suite,
                tasks=tasks,
                model=expected_model,
                host=args.host,
                freeze=False,
                force=False,
                reset_identity=not args.keep_identity,
            )
        except Exception as exc:
            raise RatchetError(f"benchmark run failed: {exc}") from exc
        after = load_results(run_dir / "results.json")

    before = load_results(args.before) if args.before else load_results(IDOS_DIR / "results.json")
    decision = decide(
        before=before,
        after=after,
        expected_n=expected_n,
        expected_model=expected_model,
        latency_budget=args.latency_budget,
        max_category_drop=args.max_category_drop,
        bootstrap=args.bootstrap,
    )

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    exp_path = EXPERIMENTS_DIR / f"{exp_id}.md"
    exp_path.write_text(
        render_experiment(
            exp_id=exp_id,
            verdict=decision.verdict,
            hypothesis=args.hypothesis,
            change=args.change,
            decision=decision,
            model=expected_model,
            suite=str(lock.get("benchmark_version")),
            pytest_ok=pytest_ok,
            run_dir=str(run_dir) if run_dir else (str(args.after) if args.after else None),
        ),
        encoding="utf-8",
    )
    print(f"[{decision.verdict}] {exp_id}")
    for reason in decision.reasons:
        print(f"  {reason}")
    print(f"  log: {exp_path}")

    if decision.keep:
        if run_dir is not None:
            freeze_idos(run_dir, force=True)
        elif args.after:
            freeze_idos(Path(args.after).parent, force=True)
        write_reports(model=expected_model, version=str(lock.get("benchmark_version") or "0.1.0"))
        if not args.no_commit:
            if pytest_ok is None:
                raise RatchetError(
                    "refusing to commit a KEEP without pytest "
                    "(drop --skip-tests, or pass --no-commit)"
                )
            artifact_files = {
                "benchmarks/idos/results.json",
                "benchmarks/idos/environment.json",
                "benchmarks/idos/summary.md",
                "benchmarks/idos/VERSION",
                "benchmarks/idos/FROZEN.md",
                "benchmarks/baseline/results.json",
                "benchmarks/baseline/environment.json",
                "benchmarks/baseline/summary.md",
                "benchmarks/baseline/VERSION",
                "benchmarks/baseline/FROZEN.md",
                "benchmarks/reports/latest.md",
                f"benchmarks/reports/benchmark-v{lock.get('benchmark_version')}.md",
                str(exp_path.relative_to(ROOT)),
                "docs/BENCHMARK.md",
                "benchmarks/docs/BENCHMARK.md",
            }
            if args.bootstrap:
                commit_files = sorted(set(collect_harness_files()) | artifact_files)
            else:
                commit_files = sorted(set(classified["allowed"]) | artifact_files)
            commit_files = [f for f in commit_files if (ROOT / f).exists()]
            commit_keep(exp_id=exp_id, decision=decision, files=commit_files, hypothesis=args.hypothesis)
            print(f"  committed on {current_branch()} {current_sha()[:10]}")
            if args.push:
                proc = _git(["push", "-u", "origin", "HEAD"], check=False)
                if proc.returncode != 0:
                    raise RatchetError(proc.stderr.strip() or "git push failed")
                print("  pushed")
        return 0

    if not args.no_revert:
        restored = restore_allowlisted(start_sha)
        print("  restored:")
        for rel in restored:
            print(f"    {rel}")
        # Keep the REVERT log even after restore.
        exp_path.write_text(
            render_experiment(
                exp_id=exp_id,
                verdict="REVERT",
                hypothesis=args.hypothesis,
                change=args.change,
                decision=decision,
                model=expected_model,
                suite=str(lock.get("benchmark_version")),
                pytest_ok=pytest_ok,
                run_dir=str(run_dir) if run_dir else (str(args.after) if args.after else None),
            ),
            encoding="utf-8",
        )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RatchetError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
