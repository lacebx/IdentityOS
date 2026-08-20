"""Build structured failure context for the ratchet autopilot coder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.invariants import ALLOWED_PREFIXES, ROOT

IDOS_RESULTS = ROOT / "benchmarks" / "idos" / "results.json"
AGENTS_MD = ROOT / "AGENTS.md"

# Real modules Gemini must edit from — not invented filenames.
KNOWN_RUNTIME_FILES = (
    "adapters/openai_adapter.py",
    "adapters/base.py",
    "adapters/groq_adapter.py",
    "core/user_profile.py",
    "core/cognitive_engine.py",
    "core/evaluation.py",
    "runtime/orchestrator.py",
    "runtime/persistence.py",
    "runtime/main.py",
    "tests/test_user_profile_remember.py",
    "tests/test_adapters.py",
    "tests/test_ratchet.py",
)


def load_results(path: Path | None = None) -> dict[str, Any]:
    p = path or IDOS_RESULTS
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def failed_tasks(results: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for task in results.get("tasks") or []:
        if task.get("success"):
            continue
        out.append(
            {
                "id": task.get("task_id"),
                "category": task.get("category"),
                "title": task.get("title"),
                "notes": task.get("notes"),
                "output_excerpt": (task.get("output") or "")[:800],
                "latency_s": task.get("latency_s"),
                "hallucination": task.get("hallucination"),
            }
        )
    return out


def category_summary(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summary = (results.get("summary") or {}) if isinstance(results.get("summary"), dict) else {}
    cats = summary.get("categories") or {}
    if cats:
        return cats
    # fallback from tasks
    buckets: dict[str, dict[str, int]] = {}
    for task in results.get("tasks") or []:
        cat = str(task.get("category") or "unknown")
        bucket = buckets.setdefault(cat, {"success": 0, "n": 0})
        bucket["n"] += 1
        if task.get("success"):
            bucket["success"] += 1
    return {
        k: {
            "success": v["success"],
            "n": v["n"],
            "success_rate": v["success"] / v["n"] if v["n"] else 0,
        }
        for k, v in buckets.items()
    }


def build_coder_prompt(
    *,
    results: dict[str, Any] | None = None,
    recent_experiments: list[dict[str, Any]] | None = None,
    max_failures: int = 12,
) -> str:
    blob = results or load_results()
    summary = blob.get("summary") or {}
    failures = failed_tasks(blob)[:max_failures]
    agents_excerpt = ""
    if AGENTS_MD.exists():
        text = AGENTS_MD.read_text(encoding="utf-8")
        agents_excerpt = text[:4000]

    allowed = "\n".join(f"  - {p}" for p in ALLOWED_PREFIXES)
    known = "\n".join(f"  - {p}" for p in KNOWN_RUNTIME_FILES)

    return (
        "You are an engineering agent improving IdentityOS runtime code for a frozen benchmark.\n"
        "The eval model is fixed (SmolLM2 via Ollama). You may ONLY change allowlisted runtime files.\n"
        "Never edit benchmarks/tasks, scoring, runner, ratchet, or task-specific hacks.\n\n"
        "CRITICAL: Only edit files that exist. Prefer paths from the known-file list below.\n"
        "There is NO adapters/ollama.py and NO runtime/agent.py — Ollama is adapters/openai_adapter.py "
        "(OllamaAdapter). Orchestration lives in runtime/orchestrator.py.\n\n"
        "## Current IDOS score\n"
        f"- success: {summary.get('success', '?')}/{summary.get('n', '?')} "
        f"({(summary.get('success_rate', 0) or 0) * 100:.0f}%)\n"
        f"- hallucination: {summary.get('hallucination', '?')}/{summary.get('n', '?')}\n"
        f"- avg latency: {summary.get('avg_latency_s', '?')}s\n\n"
        "## Category breakdown\n"
        f"{json.dumps(category_summary(blob), indent=2)}\n\n"
        "## Failed tasks (priority targets)\n"
        f"{json.dumps(failures, indent=2)}\n\n"
        "## Recent experiments (do not repeat REVERTed ideas blindly)\n"
        f"{json.dumps(recent_experiments or [], indent=2)}\n\n"
        "## Allowlisted path prefixes\n"
        f"{allowed}\n\n"
        "## Known files that exist (prefer these)\n"
        f"{known}\n\n"
        "## Engineering contract excerpt\n"
        f"{agents_excerpt}\n\n"
        "## Response format (JSON only, no markdown fences)\n"
        "{\n"
        '  "hypothesis": "one sentence why this should raise success without hurting truthfulness",\n'
        '  "change": "short list of files/subsystems touched",\n'
        '  "edits": [\n'
        '    {"path": "core/example.py", "search": "exact old text", "replace": "exact new text"}\n'
        "  ],\n"
        '  "tests_to_run": ["tests/test_example.py"]\n'
        "}\n"
        "Rules for edits:\n"
        "- paths must match allowlisted prefixes AND must currently exist in the repo\n"
        "- search must match exactly once in the file (copy exact current source)\n"
        "- prefer small, general mechanisms over benchmark-only branches\n"
        "- add or update tests when behavior changes\n"
    )


def parse_recent_experiments(limit: int = 5) -> list[dict[str, Any]]:
    exp_dir = ROOT / "benchmarks" / "experiments"
    if not exp_dir.exists():
        return []
    paths = sorted(exp_dir.glob("EXP-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in paths[:limit]:
        text = path.read_text(encoding="utf-8")
        status = "UNKNOWN"
        for line in text.splitlines():
            if line.startswith("Status:"):
                status = line.split(":", 1)[1].strip()
                break
        hypothesis = ""
        for i, line in enumerate(text.splitlines()):
            if line.strip() == "## Hypothesis" and i + 1 < len(text.splitlines()):
                hypothesis = text.splitlines()[i + 1].strip()
                break
        out.append({"id": path.stem, "status": status, "hypothesis": hypothesis})
    return out
