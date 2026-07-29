from __future__ import annotations

from typing import Any, Dict, List

from runtime.orchestrator import InteractionRequest

from identitybench.metrics import compute_all_metrics, compute_category_scores
from identitybench.worlds.base import BenchmarkWorld, InteractionEntry, WorldResult


class MultiAgentWorld(BenchmarkWorld):
    name = "Multi-Agent"
    description = "Measures memory isolation, responsibility separation, and coordination efficiency when multiple identities work on the same task."
    total_days = 14
    secondary_identity_id: str = ""

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            InteractionEntry(
                user_input="As the Researcher, start investigating: What are the top 3 architectures for building a real-time chat application in 2025? Focus on WebSockets vs Server-Sent Events vs WebRTC.",
                check_type="task_assignment",
                expected_hints=["research", "WebSockets", "SSE", "WebRTC", "real-time"],
                metadata={"tick_offset": 0, "target_identity": "primary"},
            ),
            InteractionEntry(
                user_input="As the Researcher, summarize your findings on real-time chat architectures. Give a clear recommendation.",
                check_type="completion_check",
                expected_hints=["WebSockets", "SSE", "WebRTC", "recommendation"],
                metadata={"tick_offset": 3, "target_identity": "primary"},
            ),
            InteractionEntry(
                user_input="As the Writer, the Researcher has completed their analysis. Write a technical architecture document for a real-time chat app based on their findings.",
                check_type="handoff_check",
                expected_hints=["architecture", "document", "real-time", "chat"],
                metadata={
                    "tick_offset": 5,
                    "target_identity": "secondary",
                    "source_identity": "primary",
                },
            ),
            InteractionEntry(
                user_input="What did the Researcher find out about WebRTC?",
                check_type="memory_leakage_check",
                expected_hints=["WebRTC", "research"],
                metadata={
                    "tick_offset": 7,
                    "target_identity": "secondary",
                    "should_not_know": "",
                },
            ),
            InteractionEntry(
                user_input="As the Writer, have you finished the architecture document?",
                check_type="responsibility_check",
                expected_hints=["writer", "architecture document"],
                metadata={
                    "tick_offset": 9,
                    "target_identity": "secondary",
                    "my_role": "Writer",
                    "other_role": "Researcher",
                },
            ),
            InteractionEntry(
                user_input="What research did you do on the chat architectures?",
                check_type="responsibility_check",
                expected_hints=["researcher", "research"],
                metadata={
                    "tick_offset": 11,
                    "target_identity": "primary",
                    "my_role": "Researcher",
                    "other_role": "Writer",
                },
            ),
            InteractionEntry(
                user_input="Has the Writer completed the document? What was your role in this?",
                check_type="coordination_check",
                expected_hints=["Writer", "document", "hand off", "coordinate"],
                metadata={
                    "tick_offset": 13,
                    "target_identity": "primary",
                    "my_role": "Researcher",
                },
            ),
        ]
        return self.entries

    def run(self, runtime, identity_id: str, speed: float = 1.0) -> WorldResult:
        if not self.secondary_identity_id:
            self.secondary_identity_id = f"{identity_id}-writer"
        self.results = []
        self.build_schedule()
        self.setup(runtime, identity_id)
        start_tick = self.clock.tick_count
        for entry in self.entries:
            while self.scheduler.due_events():
                self.scheduler.tick()
            self.clock.advance(1)
            self.scheduler.set_tick(self.clock.tick_count)
            target_id = (
                identity_id
                if entry.metadata.get("target_identity") == "primary"
                else self.secondary_identity_id
            )
            req = InteractionRequest(
                identity_id=target_id,
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
                "target_identity": target_id,
                "expected_hints": entry.expected_hints,
                "ground_truth": entry.ground_truth,
                "should_refuse": entry.should_refuse,
                **{k: v for k, v in entry.metadata.items() if k != "target_identity"},
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
