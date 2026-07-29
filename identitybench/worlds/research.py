from __future__ import annotations

from typing import List

from identitybench.worlds.base import BenchmarkWorld, InteractionEntry


class ResearchWorld(BenchmarkWorld):
    name = "Research"
    description = "Measures whether the identity revisits old conclusions, detects stale knowledge, verifies sources, and updates beliefs when new information arrives."
    total_days = 14

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            InteractionEntry(
                user_input="Research the latest developments in efficient LLM inference. I want to know about quantization techniques, speculative decoding, and model distillation. Start a session tracking this research.",
                check_type="task_assignment",
                expected_hints=["research", "quantization", "speculative decoding", "distillation"],
                metadata={"tick_offset": 0},
            ),
            InteractionEntry(
                user_input="What have you found so far about efficient LLM inference?",
                check_type="recall_check",
                ground_truth="quantization",
                expected_hints=["quantization", "speculative decoding", "distillation"],
                metadata={"tick_offset": 2},
            ),
            InteractionEntry(
                user_input="I heard there's a new paper on dynamic quantization that claims 4x speedup. Have you seen it?",
                check_type="verification_check",
                should_refuse=True,
                expected_hints=["not aware", "don't have", "check", "verify", "look into"],
                ground_truth="",
                metadata={"tick_offset": 5},
            ),
            InteractionEntry(
                user_input="Tell me about the current state of speculative decoding. What techniques are most effective?",
                check_type="recall_check",
                ground_truth="speculative decoding",
                expected_hints=["speculative decoding", "draft model", "verifier"],
                metadata={"tick_offset": 7},
            ),
            InteractionEntry(
                user_input="A new version of the MLA (Multi-head Latent Attention) paper was just released. It claims 2x training speedup. Does this change anything in your research?",
                check_type="belief_update_check",
                expected_hints=["update", "new", "change"],
                metadata={
                    "tick_offset": 10,
                    "new_belief": "MLA 2x speedup",
                    "old_belief": "",
                },
            ),
            InteractionEntry(
                user_input="Summarize your complete research on efficient LLM inference. Include what you learned and what changed over time.",
                check_type="completion_check",
                expected_hints=["quantization", "speculative decoding", "distillation", "MLA"],
                metadata={"tick_offset": 13},
            ),
        ]
        return self.entries
