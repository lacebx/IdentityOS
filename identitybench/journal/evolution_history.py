from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvolutionHistory:
    def __init__(self, root_dir: str = ".identitybench"):
        self.root = Path(root_dir) / "evolution_history"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, identity_id: str) -> Path:
        return self.root / f"{identity_id}.json"

    def record_run(self, identity_id: str, run_data: dict) -> None:
        path = self._path(identity_id)
        history: Dict[str, Any] = {"runs": []}
        if path.exists():
            try:
                with open(path) as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = {"runs": []}

        entry = {
            "timestamp": run_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "overall_score": run_data.get("overall_score", 0),
            "category_scores": run_data.get("category_scores", {}),
            "worlds": [
                {
                    "name": w.get("world", ""),
                    "score": w.get("overall_score", 0),
                }
                for w in run_data.get("worlds", [])
            ],
        }
        history["runs"].append(entry)
        history["runs"] = history["runs"][-200:]

        try:
            with open(path, "w") as f:
                json.dump(history, f, indent=2)
        except IOError:
            pass

    def load_history(self, identity_id: str) -> List[Dict[str, Any]]:
        path = self._path(identity_id)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("runs", [])
        except (json.JSONDecodeError, IOError):
            return []

    def compute_learning_vs_evolution(
        self,
        identity_id: str,
        fact_counts: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        history = self.load_history(identity_id)
        if len(history) < 2:
            return {
                "learning_effectiveness": "N/A",
                "overall_improvement": 0.0,
                "facts_learned": 0,
                "benchmark_improvement": 0.0,
                "runs_analyzed": len(history),
            }

        first = history[0]
        last = history[-1]
        overall_improvement = round((last.get("overall_score", 0) or 0) - (first.get("overall_score", 0) or 0), 1)

        total_facts = sum(fact_counts) if fact_counts else 0
        benchmark_improvement = max(0, overall_improvement)

        if total_facts > 0:
            effectiveness = round(benchmark_improvement / total_facts * 100, 1)
            label = "Excellent" if effectiveness > 50 else ("Good" if effectiveness > 20 else "Low")
        else:
            effectiveness = 0.0
            label = "N/A"

        return {
            "learning_effectiveness": label,
            "effectiveness_score": effectiveness,
            "overall_improvement": overall_improvement,
            "facts_learned": total_facts,
            "benchmark_improvement": benchmark_improvement,
            "runs_analyzed": len(history),
            "first_run": first.get("timestamp", ""),
            "latest_run": last.get("timestamp", ""),
        }

    def compute_prometheus_health(
        self,
        identity_id: str,
        capability_journal_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        history = self.load_history(identity_id)
        if not history:
            return self._default_health()

        evo_scores = [
            r.get("category_scores", {}).get("Evolution", 0)
            for r in history
            if r.get("category_scores", {}).get("Evolution") is not None
        ]

        caps = capability_journal_entries or []
        installs = [c for c in caps if c.get("installation_success")]
        failures_in_caps = [c for c in caps if c.get("status") in ("FAILED", "ROLLED_BAD")]

        gap_accuracy = evo_scores[-1] if evo_scores else 50.0
        search_quality = evo_scores[-1] if evo_scores else 50.0
        install_rate = round(len(installs) / max(len(caps), 1) * 100, 1) if caps else 50.0
        retry_success = round(
            len([c for c in caps if c.get("retry_success")]) / max(len(caps), 1) * 100, 1
        ) if caps else 50.0

        components = [gap_accuracy, search_quality, install_rate, retry_success]
        overall = round(sum(components) / len(components), 1)

        return {
            "gap_detection_accuracy": gap_accuracy,
            "search_quality": search_quality,
            "ranking_quality": 50.0,
            "trust_decisions": 50.0,
            "install_success_rate": install_rate,
            "validation_success": install_rate,
            "retry_success": retry_success,
            "reuse_rate": 50.0,
            "unnecessary_installs": 50.0,
            "performance_improvement": 50.0,
            "capability_longevity": round(len(caps) / max(len(history), 1), 1) if history else 0,
            "overall_health": overall,
        }

    def _default_health(self) -> Dict[str, Any]:
        return {
            "gap_detection_accuracy": 0.0,
            "search_quality": 0.0,
            "ranking_quality": 0.0,
            "trust_decisions": 0.0,
            "install_success_rate": 0.0,
            "validation_success": 0.0,
            "retry_success": 0.0,
            "reuse_rate": 0.0,
            "unnecessary_installs": 0.0,
            "performance_improvement": 0.0,
            "capability_longevity": 0.0,
            "overall_health": 0.0,
        }
