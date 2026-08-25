#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "runner.py"
MODE_B = ROOT / "research" / "mode-b"


def slugify(model: str) -> str:
    return model.replace(":", "-").replace(".", "-").replace("/", "-")


def ollama_chat(host: str, model: str, prompt: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0},
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # 4B CPU models on this host can take several minutes for first token.
    with urllib.request.urlopen(req, timeout=1200) as resp:
        return json.loads(resp.read().decode())


def smoke_test(host: str, model: str) -> dict:
    t0 = time.monotonic()
    body = ollama_chat(host, model, "Reply with exactly: OK")
    latency = time.monotonic() - t0
    text = ((body.get("message") or {}).get("content") or "").strip()
    return {"ok": True, "latency_s": round(latency, 4), "output": text, "raw": body}


def parse_artifacts(stdout: str) -> str | None:
    m = re.findall(r"\[(?:bare|idos)\] artifacts: (.+)", stdout)
    return m[-1].strip() if m else None


def run_benchmark(python_bin: str, mode: str, model: str, host: str, reset_identity: bool) -> tuple[Path, str]:
    cmd = [python_bin, str(RUNNER), "--mode", mode, "--model", model, "--host", host]
    if mode == "idos" and reset_identity:
        cmd.append("--reset-identity")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"runner failed for {mode} {model}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    artifact = parse_artifacts(proc.stdout)
    if not artifact:
        raise RuntimeError(f"could not parse artifacts path from runner output\n{proc.stdout}")
    return Path(artifact), proc.stdout


def copy_artifacts(src: Path, dest_root: Path) -> Path:
    dest = dest_root / src.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def summarize_results(results_path: Path) -> dict:
    data = json.loads(results_path.read_text())
    tasks = data.get("tasks") or []
    summary = data.get("summary") or {}
    return {
        "run_id": data.get("run_id"),
        "updated_at": data.get("updated_at"),
        "model": data.get("model"),
        "benchmark_version": data.get("benchmark_version"),
        "summary": summary,
        "tasks": tasks,
    }


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Mode B benchmark artifacts in isolated worktree.")
    ap.add_argument("--model", required=True)
    ap.add_argument("--slug", default=None)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--python-bin", default=sys.executable)
    ap.add_argument("--phase", choices=("smoke", "bare", "idos", "both"), default="both")
    args = ap.parse_args()

    slug = args.slug or slugify(args.model)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_root = MODE_B / "models" / slug
    baseline_root = MODE_B / "baselines" / slug
    idos_root = MODE_B / "idos" / slug
    runs_root = MODE_B / "runs"
    manifests_root = MODE_B / "manifests"
    for p in (model_root, baseline_root, idos_root, runs_root, manifests_root):
        p.mkdir(parents=True, exist_ok=True)

    meta: dict = {
        "timestamp": timestamp,
        "model": args.model,
        "slug": slug,
        "host": args.host,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
    }

    if args.phase in ("smoke", "both"):
        smoke = smoke_test(args.host, args.model)
        write_manifest(manifests_root / f"{timestamp}-{slug}-smoke.json", {**meta, "phase": "smoke", **smoke})
        if args.phase == "smoke":
            print(json.dumps(smoke, indent=2))
            return 0

    if args.phase in ("bare", "both"):
        bare_src, bare_stdout = run_benchmark(args.python_bin, "bare", args.model, args.host, reset_identity=False)
        bare_dest = copy_artifacts(bare_src, baseline_root)
        bare_summary = summarize_results(bare_dest / "results.json")
        write_manifest(
            manifests_root / f"{timestamp}-{slug}-bare.json",
            {
                **meta,
                "phase": "bare",
                "artifact_src": str(bare_src),
                "artifact_copy": str(bare_dest),
                "runner_stdout": bare_stdout,
                **bare_summary,
            },
        )

    if args.phase in ("idos", "both"):
        idos_src, idos_stdout = run_benchmark(args.python_bin, "idos", args.model, args.host, reset_identity=True)
        idos_dest = copy_artifacts(idos_src, idos_root)
        idos_summary = summarize_results(idos_dest / "results.json")
        write_manifest(
            manifests_root / f"{timestamp}-{slug}-idos.json",
            {
                **meta,
                "phase": "idos",
                "artifact_src": str(idos_src),
                "artifact_copy": str(idos_dest),
                "runner_stdout": idos_stdout,
                **idos_summary,
            },
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
