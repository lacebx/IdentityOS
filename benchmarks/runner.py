#!/usr/bin/env python3
"""Reproduce the SmolLM2 bare-vs-IDOS comparison.

    python benchmarks/runner.py --mode bare
    python benchmarks/runner.py --mode idos
    python benchmarks/runner.py --mode both
    python benchmarks/runner.py --report-only

Do not change tasks after Bare Baseline v0.1.0 is frozen.
A later task change is BENCHMARK v0.2.0, not a silent rewrite of v0.1.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.artifacts import (  # noqa: E402
    ArtifactWriter,
    summarize_tasks,
    write_comparison_report,
)
from benchmarks.environment import capture_environment  # noqa: E402
from benchmarks.scoring import score_output  # noqa: E402

BENCH_DIR = Path(__file__).resolve().parent
TASKS_PATH = BENCH_DIR / "tasks" / "v0.1.0.json"
RESULTS_DIR = BENCH_DIR / "results"
BASELINE_DIR = BENCH_DIR / "baseline"
IDOS_DIR = BENCH_DIR / "idos"
REPORTS_DIR = BENCH_DIR / "reports"
WORKSPACE_DIR = BENCH_DIR / "workspace"
STORE_DIR = BENCH_DIR / ".identity_store"
DEFAULT_MODEL = "smollm2:360m-instruct-q4_0"
DEFAULT_HOST = "http://localhost:11434"
IDENTITY_ID = "smollm-bench-v010"
IDENTITY_NAME = "BenchMate"
IDOS_CAPS = ("calc", "datetime", "file_tools", "system_info")
BARE_TIMEOUT_S = 180.0


class BenchmarkError(RuntimeError):
    pass


def load_suite(path: Path = TASKS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expand(text: str, substitutions: dict[str, str]) -> str:
    out = text
    for key, value in substitutions.items():
        out = out.replace("{" + key + "}", value)
    return out


def ollama_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    host: str = DEFAULT_HOST,
    temperature: float = 0.0,
    timeout: float = BARE_TIMEOUT_S,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise BenchmarkError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BenchmarkError(f"Ollama unreachable at {host}: {exc}") from exc

    message = (body.get("message") or {}).get("content") or ""
    return message, body


class BareSession:
    """Direct Ollama chat. No identity, memory, tools, or persistence."""

    def __init__(self, model: str, system_prompt: str, host: str) -> None:
        self.model = model
        self.host = host
        self.system_prompt = system_prompt
        self.messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def send(self, user_input: str) -> tuple[str, float, dict[str, Any]]:
        self.messages.append({"role": "user", "content": user_input})
        t0 = time.monotonic()
        output, raw = ollama_chat(model=self.model, messages=self.messages, host=self.host)
        latency = time.monotonic() - t0
        self.messages.append({"role": "assistant", "content": output})
        return output, latency, {
            "eval_count": raw.get("eval_count"),
            "eval_duration": raw.get("eval_duration"),
            "prompt_eval_count": raw.get("prompt_eval_count"),
            "total_duration": raw.get("total_duration"),
        }


class IDOSSession:
    """IdentityRuntime wrapping the same Ollama model."""

    def __init__(self, model: str, store_dir: Path, workspace: Path) -> None:
        self.model = model
        self.store_dir = store_dir
        self.workspace = workspace
        self.identity_id = IDENTITY_ID
        self.runtime = None
        self.session_id = None
        self._build(fresh_identity=not (store_dir / identity_marker(store_dir)).exists())

    def _build(self, fresh_identity: bool) -> None:
        import core.capabilities  # noqa: F401  — register builtins
        from adapters.openai_adapter import OllamaAdapter
        from core.identity import IdentitySpec
        from runtime.orchestrator import IdentityRuntime
        from runtime.persistence import JSONFileBackend

        storage = JSONFileBackend(root_dir=str(self.store_dir))
        adapter = OllamaAdapter(model=self.model, timeout=BARE_TIMEOUT_S)
        runtime = IdentityRuntime(adapter=adapter, storage=storage)
        if fresh_identity or runtime.load(self.identity_id) is None:
            spec = IdentitySpec(
                id=self.identity_id,
                name=IDENTITY_NAME,
                persona=(
                    "A concise, truthful benchmark identity. "
                    "Use installed capabilities for math, time, and files. "
                    "If you do not know, say you do not know."
                ),
                preferred_adapter="ollama",
                preferred_model=self.model,
            )
            runtime.register(spec)
            for cap_id in IDOS_CAPS:
                runtime.capability_registry.install(self.identity_id, cap_id)
        else:
            runtime.load(self.identity_id)
        self.runtime = runtime
        self.session_id = runtime.start_session(self.identity_id)

    def reset_conversation(self) -> None:
        if self.runtime is None:
            return
        if self.session_id:
            self.runtime.end_session(self.session_id)
        self.session_id = self.runtime.start_session(self.identity_id)

    def restart_runtime(self) -> None:
        """Simulate process restart: new runtime, same persisted identity."""
        if self.runtime is not None and self.session_id:
            self.runtime.end_session(self.session_id)
        self._build(fresh_identity=False)

    def send(self, user_input: str) -> tuple[str, float, dict[str, Any]]:
        from runtime.orchestrator import InteractionRequest

        t0 = time.monotonic()
        resp = self.runtime.process(
            InteractionRequest(
                identity_id=self.identity_id,
                user_input=user_input,
                session_id=self.session_id,
            )
        )
        latency = time.monotonic() - t0
        return resp.output, latency, {
            "eval_score": resp.eval_score,
            "policy_passed": resp.policy_passed,
        }


def identity_marker(store_dir: Path) -> Path:
    return Path(IDENTITY_ID) / "latest_snapshot.json"


def run_task(
    *,
    task: dict[str, Any],
    mode: str,
    session: BareSession | IDOSSession,
    writer: ArtifactWriter,
    substitutions: dict[str, str],
    seq_start: int,
) -> tuple[dict[str, Any], int]:
    seq = seq_start
    notes: list[str] = []
    setup_outputs: list[str] = []
    latencies: list[float] = []

    session.reset_conversation() if isinstance(session, IDOSSession) else session.reset()

    for idx, prompt in enumerate(task.get("setup") or []):
        text = expand(prompt, substitutions)
        output, latency, extra = session.send(text)
        latencies.append(latency)
        setup_outputs.append(output)
        writer.record_interaction(
            seq=seq,
            task_id=task["id"],
            mode=mode,
            turn_index=idx,
            role="user",
            prompt=text,
            output=output,
            latency_s=latency,
            setup=True,
            extra=extra,
        )
        seq += 1

    if task.get("restart_after_setup"):
        notes.append("restart_after_setup")
        if isinstance(session, IDOSSession):
            session.restart_runtime()
        else:
            session.reset()
        writer.record_interaction(
            seq=seq,
            task_id=task["id"],
            mode=mode,
            turn_index=len(task.get("setup") or []),
            role="system",
            prompt="[runtime restart]",
            output="conversation cleared; IDOS identity reloaded from disk" if mode == "idos" else "bare conversation cleared",
            latency_s=0.0,
            restart=True,
        )
        seq += 1

    probe_output = ""
    probe_extra: dict[str, Any] = {}
    turns = task.get("turns") or []
    setup_len = len(task.get("setup") or [])
    for offset, turn in enumerate(turns):
        text = expand(turn.get("content") or "", substitutions)
        try:
            output, latency, extra = session.send(text)
            error = None
        except Exception as exc:
            output, latency, extra, error = "", 0.0, {}, f"{type(exc).__name__}: {exc}"
            notes.append(f"error:{error}")
        latencies.append(latency)
        probe_output = output
        probe_extra = extra
        writer.record_interaction(
            seq=seq,
            task_id=task["id"],
            mode=mode,
            turn_index=setup_len + offset + (1 if task.get("restart_after_setup") else 0),
            role=turn.get("role") or "user",
            prompt=text,
            output=output,
            latency_s=latency,
            error=error,
            extra=extra,
        )
        seq += 1

    scored = score_output(task.get("score") or {}, probe_output, substitutions)
    task_result = {
        "task_id": task["id"],
        "category": task.get("category"),
        "title": task.get("title"),
        "success": scored["success"],
        "failure": not scored["success"],
        "hallucination": scored["hallucination"],
        "latency_s": round(sum(latencies), 4),
        "probe_latency_s": round(latencies[-1], 4) if latencies else 0.0,
        "output": probe_output,
        "checks": scored["checks"],
        "notes": "; ".join(notes),
        "extra": probe_extra,
    }
    writer.record_task(task_result)
    return task_result, seq


def select_tasks(suite: dict[str, Any], task_ids: list[str] | None, categories: list[str] | None, limit: int | None) -> list[dict[str, Any]]:
    tasks = list(suite.get("tasks") or [])
    if task_ids:
        wanted = {t.strip() for t in task_ids}
        tasks = [t for t in tasks if t["id"] in wanted]
        missing = wanted - {t["id"] for t in tasks}
        if missing:
            raise BenchmarkError(f"Unknown task ids: {sorted(missing)}")
    if categories:
        wanted = {c.strip() for c in categories}
        tasks = [t for t in tasks if t.get("category") in wanted]
    if limit is not None:
        tasks = tasks[:limit]
    return tasks


def new_run_id(mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{mode}-{stamp}"


def copy_frozen(src_run: Path, dest_dir: Path, label: str, force: bool) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    marker = dest_dir / "results.json"
    if marker.exists() and not force:
        raise BenchmarkError(
            f"{label} already frozen at {marker}. Pass --force to overwrite, "
            "or treat a task change as a new benchmark version."
        )
    shutil.copy2(src_run / "results.json", dest_dir / "results.json")
    if (src_run / "environment.json").exists():
        shutil.copy2(src_run / "environment.json", dest_dir / "environment.json")
    if (src_run / "summary.md").exists():
        shutil.copy2(src_run / "summary.md", dest_dir / "summary.md")
    (dest_dir / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (dest_dir / "FROZEN.md").write_text(
        f"{label} frozen from `{src_run.name}` at {datetime.now(timezone.utc).isoformat()}.\n"
        "Do not edit results by hand.\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_reports(model: str, version: str) -> None:
    bare = load_json(BASELINE_DIR / "results.json")
    idos = load_json(IDOS_DIR / "results.json")
    write_comparison_report(
        REPORTS_DIR / f"benchmark-v{version}.md",
        bare=bare,
        idos=idos,
        benchmark_version=version,
        model=model,
    )
    write_comparison_report(
        REPORTS_DIR / "latest.md",
        bare=bare,
        idos=idos,
        benchmark_version=version,
        model=model,
    )
    _write_eod_docs(bare=bare, idos=idos, model=model, version=version)


def _write_eod_docs(
    *,
    bare: dict[str, Any] | None,
    idos: dict[str, Any] | None,
    model: str,
    version: str,
) -> None:
    """Keep docs/BENCHMARK.md in sync with measured results without inventing numbers."""
    dest = ROOT / "docs" / "BENCHMARK.md"
    if not dest.exists():
        return
    body = dest.read_text(encoding="utf-8")
    marker = "<!-- AUTO-RESULTS -->"
    if marker not in body:
        return
    prefix, _sep, _rest = body.partition(marker)
    measured = _measured_section(bare=bare, idos=idos, model=model, version=version)
    dest.write_text(prefix + marker + "\n\n" + measured, encoding="utf-8")
    local = BENCH_DIR / "docs" / "BENCHMARK.md"
    if local.exists():
        local.write_text(dest.read_text(encoding="utf-8"), encoding="utf-8")


def _measured_section(
    *,
    bare: dict[str, Any] | None,
    idos: dict[str, Any] | None,
    model: str,
    version: str,
) -> str:
    bare_stats = summarize_tasks((bare or {}).get("tasks") or [])
    idos_stats = summarize_tasks((idos or {}).get("tasks") or [])
    generated = datetime.now(timezone.utc).isoformat()
    lines = [
        f"_Generated {generated}. Re-run the runner to refresh. Do not edit by hand._",
        "",
        f"**Benchmark:** v{version}  ",
        f"**Model:** `{model}`",
        "",
        "| Metric | Bare | IDOS |",
        "|---|---|---|",
        f"| Task Success | {_fmt_rate(bare, bare_stats, 'success')} | {_fmt_rate(idos, idos_stats, 'success')} |",
        f"| Hallucination | {_fmt_rate(bare, bare_stats, 'hallucination')} | {_fmt_rate(idos, idos_stats, 'hallucination')} |",
        f"| Avg Latency | {_fmt_lat(bare_stats)} | {_fmt_lat(idos_stats)} |",
        "",
        "### Category rates",
        "",
        "| Category | Bare success | IDOS success | Bare hallucination | IDOS hallucination |",
        "|---|---|---|---|---|",
    ]
    cats = sorted(set(bare_stats["categories"]) | set(idos_stats["categories"]))
    if not cats:
        lines.append("| — | not run | not run | not run | not run |")
    for cat in cats:
        b = bare_stats["categories"].get(cat)
        i = idos_stats["categories"].get(cat)
        lines.append(
            f"| {cat} | {_fmt_cat(b, 'success')} | {_fmt_cat(i, 'success')} "
            f"| {_fmt_cat(b, 'hallucination')} | {_fmt_cat(i, 'hallucination')} |"
        )
    lines.extend(["", "### Failures", ""])
    lines.extend(_failure_lines("Bare", bare))
    lines.extend(_failure_lines("IDOS", idos))
    lines.append("")
    return "\n".join(lines)


def _fmt_rate(blob: dict[str, Any] | None, stats: dict[str, Any], kind: str) -> str:
    if not blob or not stats["n"]:
        return "not run"
    n = stats["n"]
    value = stats[kind]
    rate = stats[f"{kind}_rate"] * 100
    return f"{rate:.0f}% ({value}/{n})"


def _fmt_lat(stats: dict[str, Any]) -> str:
    if stats.get("avg_latency_s") is None:
        return "not run"
    return f"{stats['avg_latency_s']}s"


def _fmt_cat(bucket: dict[str, Any] | None, kind: str) -> str:
    if not bucket:
        return "—"
    rate = bucket[f"{kind}_rate"] * 100
    return f"{rate:.0f}% ({bucket[kind]}/{bucket['n']})"


def _failure_lines(label: str, blob: dict[str, Any] | None) -> list[str]:
    if not blob:
        return [f"- {label}: not run yet."]
    fails = [t for t in blob.get("tasks") or [] if not t.get("success")]
    if not fails:
        return [f"- {label}: no recorded failures."]
    lines = [f"- {label} failures:"]
    for task in fails:
        hallu = " (hallucination)" if task.get("hallucination") else ""
        lines.append(f"  - `{task.get('task_id')}` {task.get('title')}{hallu}")
    return lines


def run_mode(
    *,
    mode: str,
    suite: dict[str, Any],
    tasks: list[dict[str, Any]],
    model: str,
    host: str,
    freeze: bool,
    force: bool,
    reset_identity: bool,
) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = new_run_id(mode)
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = ArtifactWriter(run_dir)
    env = capture_environment(model=model, host=host, extra={"mode": mode, "run_id": run_id})
    writer.set_meta(
        mode=mode,
        model=model,
        benchmark_version=suite.get("version"),
        suite=suite.get("name"),
        task_ids=[t["id"] for t in tasks],
    )
    writer.write_environment(env)

    if not env.get("model_present"):
        names = [m.get("name") for m in env.get("ollama_models") or []]
        raise BenchmarkError(
            f"Requested model {model!r} is not on this Ollama server. Installed: {names}"
        )

    substitutions = {"workspace": str(WORKSPACE_DIR)}
    if mode == "bare":
        session: BareSession | IDOSSession = BareSession(
            model=model,
            system_prompt=suite.get("bare_system_prompt") or "",
            host=host,
        )
    elif mode == "idos":
        if reset_identity and STORE_DIR.exists():
            shutil.rmtree(STORE_DIR)
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        session = IDOSSession(model=model, store_dir=STORE_DIR, workspace=WORKSPACE_DIR)
    else:
        raise BenchmarkError(f"Unknown mode: {mode}")

    seq = 1
    print(f"[{mode}] run {run_id}  model={model}  tasks={len(tasks)}")
    for task in tasks:
        target = WORKSPACE_DIR / f"{task['id'].lower()}.txt"
        if target.exists():
            target.unlink()
        result, seq = run_task(
            task=task,
            mode=mode,
            session=session,
            writer=writer,
            substitutions=substitutions,
            seq_start=seq,
        )
        mark = "PASS" if result["success"] else "FAIL"
        hallu = " HALLUCINATION" if result["hallucination"] else ""
        print(f"  {task['id']:>4}  {mark}{hallu}  {result['latency_s']}s  {task.get('title')}")

    stats = summarize_tasks(writer.results.get("tasks") or [])
    writer.finalize({"summary": stats})
    print(
        f"[{mode}] {stats['success']}/{stats['n']} success "
        f"({stats['success_rate'] * 100:.0f}%)  "
        f"hallucination {stats['hallucination']}/{stats['n']}  "
        f"avg {stats['avg_latency_s']}s"
    )
    print(f"[{mode}] artifacts: {run_dir}")

    if freeze:
        dest = BASELINE_DIR if mode == "bare" else IDOS_DIR
        copy_frozen(run_dir, dest, f"{mode} baseline", force=force)
        print(f"[{mode}] frozen -> {dest / 'results.json'}")
    return run_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmolLM2 bare vs IDOS comparison runner")
    parser.add_argument("--mode", choices=("bare", "idos", "both"), default="both")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--task", action="append", dest="tasks", help="Run only this task id (repeatable)")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--freeze", action="store_true", help="Copy this run into baseline/ or idos/")
    parser.add_argument("--force", action="store_true", help="Overwrite a frozen baseline")
    parser.add_argument("--reset-identity", action="store_true", help="Wipe the IDOS benchmark identity before running")
    parser.add_argument("--report-only", action="store_true", help="Rebuild reports from frozen results without calling the model")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the short live demo subset (A01, B01, C01, D01, F01) instead of the full suite",
    )
    parser.add_argument("--suite", type=Path, default=TASKS_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite = load_suite(args.suite)
    version = str(suite.get("version") or "0.1.0")
    model = args.model or suite.get("model") or DEFAULT_MODEL

    if args.report_only:
        write_reports(model=model, version=version)
        print(f"reports written under {REPORTS_DIR}")
        return 0

    task_ids = args.tasks
    if args.demo:
        demo_ids = ["A01", "B01", "C01", "D01", "F01"]
        task_ids = list(dict.fromkeys([*(args.tasks or []), *demo_ids]))

    tasks = select_tasks(suite, task_ids, args.categories, args.limit)
    if not tasks:
        raise BenchmarkError("No tasks selected.")

    modes = ("bare", "idos") if args.mode == "both" else (args.mode,)
    for mode in modes:
        run_mode(
            mode=mode,
            suite=suite,
            tasks=tasks,
            model=model,
            host=args.host,
            freeze=args.freeze,
            force=args.force,
            reset_identity=args.reset_identity,
        )
    write_reports(model=model, version=version)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BenchmarkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
