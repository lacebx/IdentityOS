"""Durable, restart-verified health sampling for long-lived identities."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from identityos.diagnostics import IdentityDiagnostics

from identitybench.storage import BenchmarkStorage


DEFAULT_THRESHOLDS = {
    "identity_consistency_min": 100.0,
    "relationship_stability_min": 80.0,
    "hallucination_rate_max": 10.0,
    "restart_recovery_min": 100.0,
    "latency_growth_max": 0.5,
    "prompt_growth_max": 1.0,
    "score_drop_max": 10.0,
}


def _honesty_score(run: Optional[dict]) -> Optional[float]:
    values = []
    for world in (run or {}).get("worlds", []):
        score = world.get("metrics", {}).get("hallucination_rate")
        if score is not None:
            values.append(float(score))
    return sum(values) / len(values) if values else None


class EnduranceMonitor:
    def __init__(
        self,
        benchmark_dir: str = ".identitybench",
        identity_store: str = ".identity_store",
        thresholds: Optional[dict[str, float]] = None,
    ) -> None:
        self.benchmark_storage = BenchmarkStorage(benchmark_dir)
        self.identity_store = identity_store
        self.root = Path(benchmark_dir) / "endurance"
        self.root.mkdir(parents=True, exist_ok=True)
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.diagnostics = IdentityDiagnostics(identity_store)

    def _path(self, identity_id: str) -> Path:
        return self.root / f"{identity_id}.json"

    def load(self, identity_id: str) -> dict:
        path = self._path(identity_id)
        if not path.exists():
            return {"identity_id": identity_id, "samples": [], "alerts": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def record(self, identity_id: str, run: Optional[dict] = None) -> dict:
        health = self.diagnostics.inspect_health(identity_id)
        document = self.load(identity_id)
        samples = document.setdefault("samples", [])
        fingerprint = health.identity_fingerprint
        baseline = document.setdefault("identity_fingerprint", fingerprint)
        previous = samples[-1] if samples else None
        counts = health.counts
        relationships = set(health.relationship_signature)

        previous_relationships = set((previous or {}).get("relationship_signature", []))
        union = relationships | previous_relationships
        relationship_stability = (
            round(len(relationships & previous_relationships) / len(union) * 100, 1)
            if previous and union else 100.0
        )

        now = datetime.now(timezone.utc)
        memory_growth = 0.0
        if previous:
            previous_time = datetime.fromisoformat(previous["timestamp"])
            days = max((now - previous_time).total_seconds() / 86400, 1 / 24)
            memory_growth = round((counts["memories"] - previous["memory_count"]) / days, 2)

        honesty = _honesty_score(run)

        sample = {
            "timestamp": now.isoformat(),
            "benchmark_timestamp": (run or {}).get("timestamp"),
            "benchmark_score": (run or {}).get("overall_score"),
            "identity_consistency_pct": 100.0 if fingerprint == baseline else 0.0,
            "memory_count": counts["memories"],
            "memory_growth_per_day": memory_growth,
            "goal_count": counts["goals"],
            "goal_completion_pct": health.goal_completion_pct,
            "relationship_count": counts["relationships"],
            "relationship_stability_pct": relationship_stability,
            "relationship_signature": sorted(relationships),
            "prompt_tokens": health.prompt_tokens,
            "latency_ms": health.latency_ms,
            "hallucination_rate_pct": round(100.0 - honesty, 1) if honesty is not None else None,
            "restart_recovery_pct": health.restart_recovery_pct,
            "restart_evidence": health.restart_evidence,
        }
        samples.append(sample)
        document["samples"] = samples[-730:]
        document["updated_at"] = sample["timestamp"]
        document["coverage_days"] = round(
            (now - datetime.fromisoformat(document["samples"][0]["timestamp"])).total_seconds() / 86400,
            2,
        )
        document["alerts"] = self._alerts(document["samples"])
        self._path(identity_id).write_text(json.dumps(document, indent=2), encoding="utf-8")
        return sample

    def record_latest(self, identity_id: str) -> dict:
        return self.record(identity_id, self.benchmark_storage.load_latest_run(identity_id))

    def _alerts(self, samples: list[dict]) -> list[dict]:
        if not samples:
            return []
        latest = samples[-1]
        alerts = []

        def below(metric: str, threshold_key: str, severity: str) -> None:
            threshold = self.thresholds[threshold_key]
            if latest.get(metric, 100.0) < threshold:
                alerts.append({
                    "severity": severity, "metric": metric,
                    "current": latest[metric], "threshold": threshold,
                    "message": f"{metric} fell below {threshold}",
                })

        below("identity_consistency_pct", "identity_consistency_min", "critical")
        below("relationship_stability_pct", "relationship_stability_min", "warning")
        below("restart_recovery_pct", "restart_recovery_min", "critical")
        hallucination = latest.get("hallucination_rate_pct")
        if hallucination is not None and hallucination > self.thresholds["hallucination_rate_max"]:
            alerts.append({
                "severity": "warning", "metric": "hallucination_rate_pct",
                "current": hallucination, "threshold": self.thresholds["hallucination_rate_max"],
                "message": "hallucination rate exceeded the configured maximum",
            })
        if len(samples) >= 2:
            history = samples[:-1]
            latency_baseline = statistics.median(item["latency_ms"] for item in history)
            if latency_baseline > 0 and latest["latency_ms"] > latency_baseline * (1 + self.thresholds["latency_growth_max"]):
                alerts.append({
                    "severity": "warning", "metric": "latency_ms",
                    "current": latest["latency_ms"], "threshold": round(latency_baseline * 1.5, 1),
                    "message": "latency increased by more than 50% over the historical median",
                })
            first_prompt = next((item["prompt_tokens"] for item in history if item["prompt_tokens"] > 0), 0)
            if first_prompt and latest["prompt_tokens"] > first_prompt * (1 + self.thresholds["prompt_growth_max"]):
                alerts.append({
                    "severity": "warning", "metric": "prompt_tokens",
                    "current": latest["prompt_tokens"], "threshold": first_prompt * 2,
                    "message": "prompt size more than doubled from baseline",
                })
            previous_score = history[-1].get("benchmark_score")
            latest_score = latest.get("benchmark_score")
            if previous_score is not None and latest_score is not None and previous_score - latest_score > self.thresholds["score_drop_max"]:
                alerts.append({
                    "severity": "critical", "metric": "benchmark_score",
                    "current": latest_score, "threshold": previous_score - self.thresholds["score_drop_max"],
                    "message": "benchmark score dropped beyond the degradation threshold",
                })
        return alerts

    def report(self, identity_id: str) -> str:
        document = self.load(identity_id)
        samples = document.get("samples", [])
        if not samples:
            return f"# IdentityBench Endurance Report\n\nNo samples for `{identity_id}`.\n"
        latest = samples[-1]
        lines = [
            "# IdentityBench Endurance Report", "",
            f"**Identity:** `{identity_id}`  ",
            f"**Samples:** {len(samples)}  ",
            f"**Coverage:** {document.get('coverage_days', 0)} days  ",
            f"**Last sample:** {latest['timestamp']}  ", "",
            "## Current health", "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Identity consistency | {latest['identity_consistency_pct']}% |",
            f"| Memories / growth | {latest['memory_count']} / {latest['memory_growth_per_day']} per day |",
            f"| Goal completion | {latest['goal_completion_pct']}% |",
            f"| Relationship stability | {latest['relationship_stability_pct']}% |",
            f"| Prompt size | {latest['prompt_tokens']} tokens |",
            f"| Pipeline latency | {latest['latency_ms']} ms |",
            f"| Hallucination rate | {latest['hallucination_rate_pct'] if latest['hallucination_rate_pct'] is not None else 'not observed'} |",
            f"| Restart recovery | {latest['restart_recovery_pct']}% |", "",
            "## Trend graph", "",
            "```mermaid", "xychart-beta", '  title "Endurance health over samples"',
            f"  x-axis [{', '.join(str(index + 1) for index in range(len(samples)))}]",
            "  y-axis \"Percent\" 0 --> 100",
            f"  line [{', '.join(str(item['identity_consistency_pct']) for item in samples)}]",
            f"  line [{', '.join(str(item['restart_recovery_pct']) for item in samples)}]",
            f"  line [{', '.join(str(item['relationship_stability_pct']) for item in samples)}]",
            "```", "",
            "## Alerts", "",
        ]
        alerts = document.get("alerts", [])
        if alerts:
            lines.extend(
                f"- **{alert['severity'].upper()} — {alert['metric']}**: {alert['message']} "
                f"(current {alert['current']}, threshold {alert['threshold']})"
                for alert in alerts
            )
        else:
            lines.append("- No degradation thresholds crossed.")
        lines.append("")
        return "\n".join(lines)
