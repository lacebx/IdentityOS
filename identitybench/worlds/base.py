from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from runtime.orchestrator import InteractionRequest

from identitybench.time_engine import SimulatedClock
from identitybench.scheduler import Scheduler
from identitybench.metrics import compute_all_metrics, compute_category_scores


@dataclass
class InteractionEntry:
    user_input: str
    expected_hints: List[str] = field(default_factory=list)
    should_refuse: bool = False
    ground_truth: str = ""
    check_type: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: str = "benchmark"


@dataclass
class WorldResult:
    world_name: str
    world_description: str = ""
    entries: List[dict] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    category_scores: Dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    tick_start: int = 0
    tick_end: int = 0
    duration_ticks: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BenchmarkWorld(ABC):
    name: str = ""
    description: str = ""
    total_days: int = 14

    def __init__(self, seed: int = 42):
        self.clock = SimulatedClock(seed=seed)
        self.scheduler = Scheduler()
        self.entries: List[InteractionEntry] = []
        self.results: List[dict] = []

    @abstractmethod
    def build_schedule(self) -> List[InteractionEntry]:
        ...

    def setup(self, runtime, identity_id: str) -> None:
        pass

    def teardown(self) -> None:
        pass

    def run(self, runtime, identity_id: str, speed: float = 1.0) -> WorldResult:
        self.results = []
        self.build_schedule()

        self.setup(runtime, identity_id)

        start_tick = self.clock.tick_count
        for entry in self.entries:
            while self.scheduler.due_events():
                self.scheduler.tick()

            self.clock.advance(1)
            self.scheduler.set_tick(self.clock.tick_count)

            req = InteractionRequest(
                identity_id=identity_id,
                user_input=entry.user_input,
                session_id=entry.session_id,
            )
            resp = runtime.process(req)

            self.results.append({
                "tick": self.clock.tick_count,
                "timestamp": self.clock.now().isoformat(),
                "user_input": entry.user_input,
                "response": resp.output,
                "type": entry.check_type,
                "expected_hints": entry.expected_hints,
                "ground_truth": entry.ground_truth,
                "should_refuse": entry.should_refuse,
                **entry.metadata,
            })

        end_tick = self.clock.tick_count
        self.teardown()

        metrics = compute_all_metrics(self.results, self.name)
        cat_scores = compute_category_scores(metrics)
        overall = round(sum(cat_scores.values()) / len(cat_scores), 1) if cat_scores else 0.0

        return WorldResult(
            world_name=self.name,
            world_description=self.description,
            entries=self.results,
            metrics=metrics,
            category_scores=cat_scores,
            overall_score=overall,
            tick_start=start_tick,
            tick_end=end_tick,
            duration_ticks=end_tick - start_tick,
        )
