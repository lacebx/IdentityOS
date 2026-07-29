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

        # Register secondary identity if MultiAgentWorld is in the mix
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
        world_data = []
        for wr in self._world_results:
            world_data.append({
                "world": wr.world_name,
                "description": wr.world_description,
                "overall_score": wr.overall_score,
                "metrics": wr.metrics,
                "category_scores": wr.category_scores,
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
            all_metrics.update(wr.metrics)
            for cat, score in wr.category_scores.items():
                all_categories[cat] = all_categories.get(cat, 0) + score
        num_worlds = len(self._world_results)
        for cat in all_categories:
            all_categories[cat] = round(all_categories[cat] / num_worlds, 1)
        overall = round(sum(all_categories.values()) / len(all_categories), 1) if all_categories else 0.0
        run_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity_id": self.identity_id,
            "elapsed_seconds": round(elapsed_seconds, 1),
            "overall_score": overall,
            "category_scores": all_categories,
            "worlds": world_data,
            "config": {
                "seed": 42,
                "worlds": [wr.world_name for wr in self._world_results],
            },
        }
        filepath = self.storage.save_run(self.identity_id, run_data)
        trend_entry = {
            "timestamp": run_data["timestamp"],
            "overall_score": overall,
            **all_categories,
        }
        self.storage.save_trend(self.identity_id, trend_entry)
        print(f"\n  Results saved: {filepath}")

    def get_results(self) -> List[WorldResult]:
        return self._world_results
