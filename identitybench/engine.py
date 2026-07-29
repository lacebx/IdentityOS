from __future__ import annotations

import os
import sys
import time as real_time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend

from identitybench.storage import BenchmarkStorage
from identitybench.worlds.base import BenchmarkWorld, WorldResult
from identitybench.worlds.research import ResearchWorld
from identitybench.worlds.project import ProjectWorld
from identitybench.worlds.assistant import AssistantWorld
from identitybench.worlds.knowledge import KnowledgeWorld
from identitybench.worlds.multi_agent import MultiAgentWorld
from identitybench.worlds.trust import TrustWorld
from identitybench.worlds.evolution import EvolutionWorld
from identitybench.metrics import (
    compute_all_metrics,
    compute_category_scores,
    compute_category_explanations,
)
from identitybench.journal.capability_journal import CapabilityJournal
from identitybench.journal.evolution_history import EvolutionHistory
from identitybench.analytics.diff import compute_benchmark_diff
from identitybench.analytics.regression import detect_regressions
from identitybench.analytics.recommendations import generate_recommendations
from identitybench.analytics.roi import calculate_capability_roi
from identitybench.analytics.root_cause import analyze_root_causes
from identitybench.analytics.timeline import build_evolution_timeline


DEFAULT_WORLDS: List[Type[BenchmarkWorld]] = [
    ResearchWorld,
    ProjectWorld,
    AssistantWorld,
    KnowledgeWorld,
    TrustWorld,
    MultiAgentWorld,
    EvolutionWorld,
]

SMOKE_WORLDS: List[Type[BenchmarkWorld]] = [
    EvolutionWorld,
    TrustWorld,
    ResearchWorld,
]


class IdentityBench:
    def __init__(
        self,
        identity_id: str,
        storage: Optional[BenchmarkStorage] = None,
        runtime: Optional[IdentityRuntime] = None,
        storage_path: str = ".identitybench",
    ):
        self.identity_id = identity_id
        self.storage = storage or BenchmarkStorage(storage_path)
        self.runtime = runtime
        self._world_results: List[WorldResult] = []
        self.capability_journal = CapabilityJournal(storage_path)
        self.evolution_history = EvolutionHistory(storage_path)

    def load_identity(self, identity_id: Optional[str] = None) -> None:
        target = identity_id or self.identity_id
        if not self.runtime:
            storage_backend = JSONFileBackend(root_dir=".identity_store")
            self.runtime = IdentityRuntime(storage=storage_backend)
            count = self.runtime.load_persisted()
        spec = self.runtime.load(target)
        if not spec:
            raise ValueError(
                f"Identity '{target}' not found. "
                f"Available: {[s.id for s in self.runtime.identity_store.list_all()]} or run 'identity list'."
            )

    def run(
        self,
        world_classes: Optional[List[Type[BenchmarkWorld]]] = None,
        speed: float = 1.0,
        seed: int = 42,
    ) -> Dict[str, WorldResult]:
        if world_classes is None:
            world_classes = DEFAULT_WORLDS
        if not self.runtime:
            self.load_identity()

        for cls in world_classes:
            if cls is MultiAgentWorld and self.runtime:
                secondary_id = f"{self.identity_id}-writer"
                if not self.runtime.load(secondary_id):
                    from core.identity import create_identity
                    spec = create_identity(name="Writer", identity_id=secondary_id, persona="technical writer")
                    self.runtime.register(spec)

        results: Dict[str, WorldResult] = {}
        total = len(world_classes)
        start_wall = real_time.time()

        for idx, cls in enumerate(world_classes, 1):
            print(f"  [{idx}/{total}] {cls.name}...", end=" ", flush=True)
            try:
                world = cls(seed=seed)
                result = world.run(self.runtime, self.identity_id, speed=speed)
                results[cls.name] = result
                score = result.overall_score
                print(f"overall={score}")
            except Exception as e:
                print(f"FAILED ({e})")
                import traceback
                traceback.print_exc()
                results[cls.name] = WorldResult(
                    world_name=cls.name,
                    overall_score=0.0,
                )

        elapsed = real_time.time() - start_wall
        self._world_results = list(results.values())
        self._save_results(elapsed)
        return results

    def _save_results(self, elapsed_seconds: float) -> None:
        all_metrics: Dict[str, float] = {}
        all_categories: Dict[str, float] = {}
        all_explanations: Dict[str, Dict[str, list]] = {}
        world_data = []
        for wr in self._world_results:
            metrics = wr.metrics
            cats = wr.category_scores
            world_data.append({
                "world": wr.world_name,
                "description": wr.world_description,
                "overall_score": wr.overall_score,
                "metrics": metrics,
                "category_scores": cats,
                "entries": [
                    {
                        "tick": e["tick"],
                        "type": e["type"],
                        "user_input": e.get("user_input", ""),
                        "response": e.get("response", ""),
                    }
                    for e in wr.entries
                ],
            })
            all_metrics.update(metrics)
            for cat, score in cats.items():
                all_categories[cat] = all_categories.get(cat, 0) + score
            
            try:
                explanations = compute_category_explanations(
                    [{"type": e["type"], "response": e.get("response", "")}
                     for e in wr.entries],
                    wr.world_name,
                )
                for cat, exp in explanations.items():
                    if cat not in all_explanations:
                        all_explanations[cat] = {"reasons": [], "confidence": 1.0, "evidence_count": 0}
                    all_explanations[cat]["reasons"].extend(exp.get("reasons", []))
                    all_explanations[cat]["evidence_count"] += exp.get("evidence_count", 0)
                    all_explanations[cat]["confidence"] = min(
                        all_explanations[cat]["confidence"],
                        exp.get("confidence", 0.5),
                    )
            except Exception:
                pass

        num_worlds = len(self._world_results)
        for cat in all_categories:
            all_categories[cat] = round(all_categories[cat] / num_worlds, 1)
        overall = round(sum(all_categories.values()) / len(all_categories), 1) if all_categories else 0.0
        
        # Load previous run for diff
        prev_run = self.storage.load_latest_run(self.identity_id)
        capability_history = self.capability_journal.list_capabilities(self.identity_id)
        cap_entries = []
        for cap_id in capability_history:
            cap_entries.extend(self.capability_journal.get_journal(self.identity_id, cap_id))

        run_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity_id": self.identity_id,
            "elapsed_seconds": round(elapsed_seconds, 1),
            "overall_score": overall,
            "category_scores": all_categories,
            "explanations": all_explanations,
            "worlds": world_data,
            "config": {
                "seed": 42,
                "worlds": [wr.world_name for wr in self._world_results],
            },
        }

        # Analytics
        if prev_run:
            diff = compute_benchmark_diff(prev_run, run_data)
            run_data["diff_vs_previous"] = diff
            trends = self.storage.load_trends(self.identity_id)
            regressions = detect_regressions(trends) if trends else []
            run_data["regressions"] = regressions
            root_causes = analyze_root_causes(diff, prev_run, run_data, cap_entries)
            run_data["root_causes"] = root_causes
            run_data["recommendations"] = generate_recommendations(
                cat_scores=all_categories,
                trends=trends,
                regressions=regressions,
                capability_history=cap_entries,
            )

        filepath = self.storage.save_run(self.identity_id, run_data)
        trend_entry = {
            "timestamp": run_data["timestamp"],
            "overall_score": overall,
            **all_categories,
        }
        self.storage.save_trend(self.identity_id, trend_entry)
        self.evolution_history.record_run(self.identity_id, run_data)
        print(f"\n  Results saved: {filepath}")

    def get_results(self) -> List[WorldResult]:
        return self._world_results
