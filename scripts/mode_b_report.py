#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODE_B = ROOT / "research" / "mode-b"
MANIFESTS = MODE_B / "manifests"


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def latest_by_phase() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for path in sorted(MANIFESTS.glob("*.json")):
        data = load_manifest(path)
        key = (data["slug"], data["phase"])
        prev = out.get(key)
        if not prev or data["timestamp"] > prev["timestamp"]:
            out[key] = data
    return out


def task_map(manifest: dict) -> dict[str, dict]:
    return {t["task_id"]: t for t in manifest.get("tasks") or []}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    latest = latest_by_phase()
    rows: list[str] = []
    task_ids = ["A05", "C01", "C02", "D04", "E01", "E02", "E03"]
    slugs = sorted({slug for slug, _ in latest})

    rows.append("# Cross-model results\n")
    rows.append("| Model | Bare | IDOS | Δ tasks | Hallucinations Bare | Hallucinations IDOS | Avg latency Bare | Avg latency IDOS |")
    rows.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for slug in slugs:
        bare = latest.get((slug, "bare"))
        idos = latest.get((slug, "idos"))
        if not bare or not idos:
            rows.append(f"| {slug} | pending | pending | — | — | — | — | — |")
            continue
        bs = bare["summary"]
        is_ = idos["summary"]
        delta = is_["success"] - bs["success"]
        rows.append(
            f"| {slug} | {bs['success']}/{bs['n']} | {is_['success']}/{is_['n']} | {delta:+d} | "
            f"{bs['hallucination']}/{bs['n']} | {is_['hallucination']}/{is_['n']} | "
            f"{bs['avg_latency_s']}s | {is_['avg_latency_s']}s |"
        )

    rows.append("\n## Failure matrix\n")
    header = "| Task | Category | " + " | ".join(slugs or ["pending"]) + " |"
    sep = "|---|---|" + "|".join(["---"] * max(1, len(slugs))) + "|"
    rows.append(header)
    rows.append(sep)
    categories = {"A05": "reasoning", "C01": "tools", "C02": "tools", "D04": "persistence", "E01": "long_task", "E02": "long_task", "E03": "long_task"}
    for task_id in task_ids:
        vals = []
        for slug in slugs:
            idos = latest.get((slug, "idos"))
            if not idos:
                vals.append("pending")
                continue
            task = task_map(idos).get(task_id)
            vals.append("PASS" if task and task.get("success") else "FAIL")
        rows.append(f"| {task_id} | {categories[task_id]} | " + " | ".join(vals or ["pending"]) + " |")

    write_text(MODE_B / "analysis" / "CROSS_MODEL_RESULTS.md", "\n".join(rows) + "\n")
    write_text(MODE_B / "experiments" / "INDEX.md", "# Mode B experiment index\n\nInitial baselines and first IDOS comparisons are tracked via manifests under `research/mode-b/manifests/`.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
