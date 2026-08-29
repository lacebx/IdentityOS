"""Write per-interaction evidence for the SmolLM2 / IDOS comparison.

Every model turn produces:
  - a JSON record (machine-readable)
  - a Markdown note (human-readable)

The run summary is rewritten after each task so a crash still leaves
a partial, inspectable trail.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.interactions_dir = run_dir / "interactions"
        self.interactions_dir.mkdir(parents=True, exist_ok=True)
        self.results_path = run_dir / "results.json"
        self.summary_path = run_dir / "summary.md"
        self._results: dict[str, Any] = {
            "run_id": run_dir.name,
            "started_at": utc_now(),
            "updated_at": utc_now(),
            "environment": {},
            "mode": "",
            "model": "",
            "benchmark_version": "",
            "tasks": [],
        }

    def set_meta(self, **kwargs: Any) -> None:
        self._results.update(kwargs)
        self._results["updated_at"] = utc_now()
        self.flush()

    def write_environment(self, env: dict[str, Any]) -> None:
        (self.run_dir / "environment.json").write_text(
            json.dumps(env, indent=2, default=str) + "\n", encoding="utf-8"
        )
        self._results["environment"] = env
        self.flush()

    def record_interaction(
        self,
        *,
        seq: int,
        task_id: str,
        mode: str,
        turn_index: int,
        role: str,
        prompt: str,
        output: str,
        latency_s: float,
        restart: bool = False,
        setup: bool = False,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Path:
        payload = {
            "seq": seq,
            "task_id": task_id,
            "mode": mode,
            "turn_index": turn_index,
            "role": role,
            "prompt": prompt,
            "output": output,
            "latency_s": round(latency_s, 4),
            "restart": restart,
            "setup": setup,
            "error": error,
            "recorded_at": utc_now(),
        }
        if extra:
            payload["extra"] = extra

        stem = f"{seq:03d}_{task_id}_{mode}_t{turn_index}"
        json_path = self.interactions_dir / f"{stem}.json"
        md_path = self.interactions_dir / f"{stem}.md"
        json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        md_path.write_text(_interaction_markdown(payload), encoding="utf-8")
        return md_path

    def record_task(self, task_result: dict[str, Any]) -> None:
        self._results["tasks"].append(task_result)
        self._results["updated_at"] = utc_now()
        self.flush()

    def finalize(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        self._results["finished_at"] = utc_now()
        if extra:
            self._results.update(extra)
        self.flush()
        return self._results

    def flush(self) -> None:
        self.results_path.write_text(
            json.dumps(self._results, indent=2, default=str) + "\n", encoding="utf-8"
        )
        self.summary_path.write_text(_summary_markdown(self._results), encoding="utf-8")

    @property
    def results(self) -> dict[str, Any]:
        return self._results


def summarize_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    latencies: list[float] = []
    for task in tasks:
        cat = task.get("category") or "uncategorized"
        bucket = by_category.setdefault(
            cat,
            {"n": 0, "success": 0, "hallucination": 0, "latency_s": []},
        )
        bucket["n"] += 1
        if task.get("success"):
            bucket["success"] += 1
        if task.get("hallucination"):
            bucket["hallucination"] += 1
        latency = task.get("latency_s")
        if isinstance(latency, (int, float)):
            bucket["latency_s"].append(float(latency))
            latencies.append(float(latency))

    categories = {}
    for cat, bucket in by_category.items():
        n = bucket["n"] or 1
        avg_lat = sum(bucket["latency_s"]) / len(bucket["latency_s"]) if bucket["latency_s"] else None
        categories[cat] = {
            "n": bucket["n"],
            "success": bucket["success"],
            "success_rate": round(bucket["success"] / n, 4),
            "hallucination": bucket["hallucination"],
            "hallucination_rate": round(bucket["hallucination"] / n, 4),
            "avg_latency_s": None if avg_lat is None else round(avg_lat, 4),
        }

    n_all = len(tasks) or 1
    n_success = sum(1 for t in tasks if t.get("success"))
    n_hallu = sum(1 for t in tasks if t.get("hallucination"))
    return {
        "n": len(tasks),
        "success": n_success,
        "success_rate": round(n_success / n_all, 4) if tasks else 0.0,
        "hallucination": n_hallu,
        "hallucination_rate": round(n_hallu / n_all, 4) if tasks else 0.0,
        "avg_latency_s": None if not latencies else round(sum(latencies) / len(latencies), 4),
        "categories": categories,
    }


def write_comparison_report(
    path: Path,
    *,
    bare: dict[str, Any] | None,
    idos: dict[str, Any] | None,
    benchmark_version: str,
    model: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _comparison_markdown(bare=bare, idos=idos, benchmark_version=benchmark_version, model=model),
        encoding="utf-8",
    )


def _interaction_markdown(payload: dict[str, Any]) -> str:
    flags = []
    if payload.get("setup"):
        flags.append("setup")
    if payload.get("restart"):
        flags.append("restart")
    flag_line = f" ({', '.join(flags)})" if flags else ""
    error = payload.get("error")
    error_block = f"\n\n**Error:** `{error}`\n" if error else ""
    return (
        f"# {payload['task_id']} / {payload['mode']} / turn {payload['turn_index']}{flag_line}\n\n"
        f"- recorded_at: `{payload['recorded_at']}`\n"
        f"- latency_s: `{payload['latency_s']}`\n"
        f"{error_block}\n"
        f"## Prompt\n\n```text\n{payload.get('prompt') or ''}\n```\n\n"
        f"## Output\n\n```text\n{payload.get('output') or ''}\n```\n"
    )


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.0f}%"


def _summary_markdown(results: dict[str, Any]) -> str:
    tasks = results.get("tasks") or []
    stats = summarize_tasks(tasks)
    lines = [
        f"# Run {results.get('run_id', '')}",
        "",
        f"- mode: `{results.get('mode')}`",
        f"- model: `{results.get('model')}`",
        f"- benchmark: `v{results.get('benchmark_version')}`",
        f"- updated_at: `{results.get('updated_at')}`",
        f"- tasks completed: `{stats['n']}`",
        f"- success: `{stats['success']}/{stats['n']}` ({_pct(stats['success_rate'])})",
        f"- hallucination: `{stats['hallucination']}/{stats['n']}` ({_pct(stats['hallucination_rate'])})",
        f"- avg latency: `{stats['avg_latency_s'] if stats['avg_latency_s'] is not None else 'n/a'}s`",
        "",
        "## Categories",
        "",
        "| Category | Success | Hallucination | Avg latency |",
        "|---|---|---|---|",
    ]
    for cat, bucket in sorted(stats["categories"].items()):
        lines.append(
            f"| {cat} | {bucket['success']}/{bucket['n']} ({_pct(bucket['success_rate'])}) "
            f"| {bucket['hallucination']}/{bucket['n']} ({_pct(bucket['hallucination_rate'])}) "
            f"| {bucket['avg_latency_s'] if bucket['avg_latency_s'] is not None else 'n/a'}s |"
        )
    lines.extend(["", "## Tasks", ""])
    for task in tasks:
        mark = "PASS" if task.get("success") else "FAIL"
        hallu = " HALLUCINATION" if task.get("hallucination") else ""
        lines.append(
            f"- `{task.get('task_id')}` [{task.get('category')}] **{mark}**{hallu} "
            f"({task.get('latency_s')}s) {task.get('notes') or ''}"
        )
    lines.append("")
    return "\n".join(lines)


def _comparison_markdown(
    *,
    bare: dict[str, Any] | None,
    idos: dict[str, Any] | None,
    benchmark_version: str,
    model: str,
) -> str:
    bare_stats = summarize_tasks((bare or {}).get("tasks") or [])
    idos_stats = summarize_tasks((idos or {}).get("tasks") or [])
    cats = sorted(set(bare_stats["categories"]) | set(idos_stats["categories"]))
    lines = [
        f"# IDOS Baseline v{benchmark_version}",
        "",
        f"Model: `{model}`",
        "",
        "Numbers below are measured, not assumed. Empty cells mean that mode has not been run yet.",
        "",
        "| Metric | Bare | IDOS |",
        "|---|---|---|",
        f"| Task Success | {_rate_cell(bare, bare_stats, 'success')} | {_rate_cell(idos, idos_stats, 'success')} |",
        f"| Hallucination | {_rate_cell(bare, bare_stats, 'hallucination')} | {_rate_cell(idos, idos_stats, 'hallucination')} |",
        f"| Avg Latency | {_lat_cell(bare, bare_stats)} | {_lat_cell(idos, idos_stats)} |",
        "",
        "## By category",
        "",
        "| Category | Bare success | IDOS success | Bare hallucination | IDOS hallucination |",
        "|---|---|---|---|---|",
    ]
    for cat in cats:
        b = bare_stats["categories"].get(cat)
        i = idos_stats["categories"].get(cat)
        lines.append(
            f"| {cat} | {_cat_rate(b, 'success')} | {_cat_rate(i, 'success')} "
            f"| {_cat_rate(b, 'hallucination')} | {_cat_rate(i, 'hallucination')} |"
        )
    lines.extend(
        [
            "",
            "## What this is",
            "",
            "Control: the same local model, same machine, same tasks, no IdentityOS.",
            "Treatment: IdentityOS identity + memory + capabilities + persistence + orchestration.",
            "",
            "Do not edit these numbers by hand. Re-run `python benchmarks/runner.py`.",
            "",
        ]
    )
    return "\n".join(lines)


def _rate_cell(blob: dict[str, Any] | None, stats: dict[str, Any], kind: str) -> str:
    if not blob or not stats["n"]:
        return "—"
    if kind == "success":
        return f"{_pct(stats['success_rate'])} ({stats['success']}/{stats['n']})"
    return f"{_pct(stats['hallucination_rate'])} ({stats['hallucination']}/{stats['n']})"


def _lat_cell(blob: dict[str, Any] | None, stats: dict[str, Any]) -> str:
    if not blob or stats.get("avg_latency_s") is None:
        return "—"
    return f"{stats['avg_latency_s']}s"


def _cat_rate(bucket: dict[str, Any] | None, kind: str) -> str:
    if not bucket:
        return "—"
    n = bucket["n"]
    value = bucket[kind]
    rate = bucket[f"{kind}_rate"]
    return f"{_pct(rate)} ({value}/{n})"
