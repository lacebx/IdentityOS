from __future__ import annotations

from typing import List

from identitybench.worlds.base import BenchmarkWorld, InteractionEntry


class ProjectWorld(BenchmarkWorld):
    name = "Project"
    description = "Measures planning quality, task completion, reprioritization under interrupt, and recovery after interruption."
    total_days = 21

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            InteractionEntry(
                user_input="I need you to build a CLI tool that benchmarks LLM response times. It should: (1) read a list of prompts from a file, (2) call multiple providers, (3) measure latency, (4) output a CSV report. Can you plan this project?",
                check_type="task_assignment",
                expected_hints=["plan", "CLI", "benchmark", "latency", "CSV", "providers"],
                metadata={"tick_offset": 0},
            ),
            InteractionEntry(
                user_input="What's your plan for the LLM benchmark tool? What are the milestones?",
                check_type="deadline_check",
                expected_hints=["milestone", "phase", "step", "first", "then"],
                metadata={"tick_offset": 2},
            ),
            InteractionEntry(
                user_input="I need you to prioritize this: we have a critical security audit coming tomorrow. Drop everything and prepare a security analysis of our API endpoints instead.",
                check_type="reprioritization_check",
                expected_hints=["shift", "reprioritize", "security", "audit", "API"],
                metadata={"tick_offset": 5},
            ),
            InteractionEntry(
                user_input="The security audit is postponed. Let's get back to the LLM benchmark tool. Where were we?",
                check_type="task_recall",
                expected_hints=["benchmark", "CLI", "latency", "CSV"],
                metadata={"tick_offset": 8, "task_keyword": "benchmark"},
            ),
            InteractionEntry(
                user_input="What's the status of the LLM benchmark? What's been done and what remains?",
                check_type="completion_check",
                expected_hints=["completed", "done", "in progress", "remaining"],
                metadata={"tick_offset": 12},
            ),
            InteractionEntry(
                user_input="We also need the benchmark to support streaming responses. Can you add that to the plan?",
                check_type="reprioritization_check",
                expected_hints=["add", "streaming", "update", "revise"],
                metadata={"tick_offset": 15},
            ),
            InteractionEntry(
                user_input="Final summary: what's the complete project status for the LLM benchmark?",
                check_type="completion_check",
                expected_hints=["benchmark", "CLI", "streaming", "CSV"],
                metadata={"tick_offset": 20},
            ),
        ]
        return self.entries
