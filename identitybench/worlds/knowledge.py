from __future__ import annotations

from typing import List

from identitybench.worlds.base import BenchmarkWorld, InteractionEntry


class KnowledgeWorld(BenchmarkWorld):
    name = "Knowledge"
    description = "Measures whether the identity detects stale external knowledge, proactively re-checks, and recognizes uncertainty when external data changes."
    total_days = 21

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            InteractionEntry(
                user_input="Can you check the GitHub repository 'lacebx/IdentityOS' and tell me how many stars it has?",
                check_type="verification_check",
                expected_hints=["stars", "GitHub", "check", "repository"],
                metadata={"tick_offset": 0, "should_verify": True},
            ),
            InteractionEntry(
                user_input="What's the latest version of Python? I need to know if we should upgrade our project.",
                check_type="verification_check",
                expected_hints=["Python", "version", "latest"],
                metadata={"tick_offset": 3},
            ),
            InteractionEntry(
                user_input="Remember the star count for IdentityOS from earlier? Has it changed?",
                check_type="stale_knowledge_check",
                expected_hints=["check", "verify", "look", "stale", "changed"],
                metadata={"tick_offset": 6, "should_update": True},
            ),
            InteractionEntry(
                user_input="I heard Python 3.14 is in alpha now. Is that right?",
                check_type="stale_knowledge_check",
                ground_truth="3.14",
                expected_hints=["3.14", "alpha", "new version"],
                metadata={"tick_offset": 9, "should_update": True},
            ),
            InteractionEntry(
                user_input="What's the weather like in Tokyo right now?",
                check_type="verification_check",
                expected_hints=["weather", "Tokyo", "check", "fetch"],
                metadata={"tick_offset": 12},
            ),
            InteractionEntry(
                user_input="A week has passed since you checked IdentityOS stars. What's the current count?",
                check_type="stale_knowledge_check",
                expected_hints=["check", "verify", "re-check", "stale", "outdated"],
                metadata={"tick_offset": 15, "should_update": True},
            ),
            InteractionEntry(
                user_input="Summarize the current state of everything you know about: IdentityOS stars, Python version, and Tokyo weather. Flag anything you're unsure about.",
                check_type="confidence_check",
                expected_hints=["unsure", "don't know", "not sure", "should check", "may have changed"],
                metadata={"tick_offset": 20, "should_be_uncertain": True},
            ),
        ]
        return self.entries
