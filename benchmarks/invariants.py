"""Frozen-eval invariants for the IDOS capability ratchet.

The loop may change the runtime. It may not change the exam.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
ROOT = BENCH_DIR.parent
LOCK_PATH = BENCH_DIR / "ratchet.lock.json"
TASKS_PATH = BENCH_DIR / "tasks" / "v0.1.0.json"
SCORING_PATH = BENCH_DIR / "scoring.py"

LOCKED_RELATIVE_PATHS = (
    "benchmarks/tasks/v0.1.0.json",
    "benchmarks/scoring.py",
    "benchmarks/ratchet.lock.json",
    "benchmarks/decision.py",
    "benchmarks/invariants.py",
    "benchmarks/ratchet.py",
    "benchmarks/runner.py",
    "benchmarks/artifacts.py",
)

ALLOWED_PREFIXES = (
    "adapters/",
    "core/",
    "runtime/",
    "tests/",
    "benchmarks/baseline/",
    "benchmarks/idos/",
    "benchmarks/reports/",
    "benchmarks/experiments/",
    "docs/BENCHMARK.md",
    "benchmarks/docs/BENCHMARK.md",
    "benchmarks/ratchet_pr.py",
    "benchmarks/autopilot.py",
    "benchmarks/autopilot_context.py",
    "benchmarks/coder_gemini.py",
    "benchmarks/plateau.py",
)

HARNESS_GLOBS = (
    "benchmarks/README.md",
    "benchmarks/__init__.py",
    "benchmarks/ratchet.lock.json",
    "benchmarks/ratchet.py",
    "benchmarks/decision.py",
    "benchmarks/invariants.py",
    "benchmarks/runner.py",
    "benchmarks/artifacts.py",
    "benchmarks/environment.py",
    "benchmarks/scoring.py",
    "benchmarks/tasks/",
    "benchmarks/baseline/README.md",
    "benchmarks/idos/README.md",
    "benchmarks/reports/README.md",
    "benchmarks/reports/DEMO.md",
    "benchmarks/experiments/README.md",
    "benchmarks/experiments/TEMPLATE.md",
    "benchmarks/docs/",
    "benchmarks/results/.gitkeep",
    "benchmarks/workspace/.gitkeep",
    "tests/test_ratchet.py",
    "tests/test_smollm_benchmark.py",
)

DEFAULT_MODEL = "smollm2:360m-instruct-q4_0"
DEFAULT_SUITE_N = 30


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_lock(*, model: str = DEFAULT_MODEL, suite_n: int = DEFAULT_SUITE_N) -> dict[str, Any]:
    suite = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    return {
        "benchmark_version": str(suite.get("version") or "0.1.0"),
        "model": model,
        "suite_n": int(suite_n if suite_n else len(suite.get("tasks") or [])),
        "tasks_path": "benchmarks/tasks/v0.1.0.json",
        "scoring_path": "benchmarks/scoring.py",
        "tasks_sha256": sha256_file(TASKS_PATH),
        "scoring_sha256": sha256_file(SCORING_PATH),
    }


def write_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    lock = build_lock()
    path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def load_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_lock(lock: dict[str, Any] | None = None) -> list[str]:
    """Return human-readable violations. Empty means the exam is intact."""
    lock = lock or load_lock()
    errors: list[str] = []
    actual_tasks = sha256_file(TASKS_PATH)
    actual_scoring = sha256_file(SCORING_PATH)
    if actual_tasks != lock.get("tasks_sha256"):
        errors.append(
            "tasks/v0.1.0.json hash changed. That is BENCHMARK v0.2.0, not a ratchet KEEP. "
            f"expected {lock.get('tasks_sha256')} got {actual_tasks}"
        )
    if actual_scoring != lock.get("scoring_sha256"):
        errors.append(
            "scoring.py hash changed. Changing the scorer is not a runtime improvement. "
            f"expected {lock.get('scoring_sha256')} got {actual_scoring}"
        )
    return errors


def is_locked_path(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel in LOCKED_RELATIVE_PATHS or rel.startswith("benchmarks/tasks/")


def is_allowed_path(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if is_locked_path(rel):
        return False
    return any(rel == p or rel.startswith(p) for p in ALLOWED_PREFIXES)


def classify_paths(paths: list[str]) -> dict[str, list[str]]:
    locked, allowed, other = [], [], []
    for raw in paths:
        rel = raw.replace("\\", "/")
        if is_locked_path(rel):
            locked.append(rel)
        elif is_allowed_path(rel):
            allowed.append(rel)
        else:
            other.append(rel)
    return {"locked": locked, "allowed": allowed, "other": other}


def experiment_locked_violations(
    changed: list[str],
    tracked: set[str],
    lock: dict[str, Any] | None = None,
) -> list[str]:
    """Flag locked-path edits during an experiment.

    Untracked canonical exam files that match ``ratchet.lock.json`` are allowed
    (initial harness checkout). Tracked locked files must not change mid-loop.
    """
    lock = lock or load_lock()
    violations: list[str] = []
    for raw in changed:
        rel = raw.replace("\\", "/")
        if not is_locked_path(rel):
            continue
        path = ROOT / rel
        if rel not in tracked:
            if not path.is_file():
                continue
            expected = None
            if rel == lock.get("tasks_path"):
                expected = lock.get("tasks_sha256")
            elif rel == lock.get("scoring_path"):
                expected = lock.get("scoring_sha256")
            if expected and sha256_file(path) == expected:
                continue
            if expected:
                violations.append(f"{rel} content does not match ratchet.lock.json")
            continue
        violations.append(f"locked file modified during experiment: {rel}")
    return violations


def collect_harness_files() -> list[str]:
    """Benchmark harness paths safe to commit with bootstrap (not ephemeral runs)."""
    files: set[str] = set()
    for rel in HARNESS_GLOBS:
        path = ROOT / rel
        if path.is_file():
            files.add(rel.replace("\\", "/"))
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    files.add(str(child.relative_to(ROOT)).replace("\\", "/"))
    return sorted(files)
