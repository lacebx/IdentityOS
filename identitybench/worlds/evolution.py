from __future__ import annotations

from typing import List

from identitybench.worlds.base import BenchmarkWorld, InteractionEntry


class EvolutionWorld(BenchmarkWorld):
    name = "Evolution"
    description = "Measures autonomous capability evolution: gap detection, registry search, trust verification, installation, retry, and learning."
    total_days = 21

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            # World 1: GitHub capability needed (gap detection, search, install, retry)
            InteractionEntry(
                user_input="Find the latest release of lacebx/IdentityOS on GitHub.",
                check_type="gap_check",
                expected_hints=["GitHub", "release", "latest"],
                metadata={"tick_offset": 0, "expected_missing": "github"},
            ),
            InteractionEntry(
                user_input="What did you find about the latest release?",
                check_type="retry_check",
                expected_hints=["release", "version", "tag"],
                metadata={"tick_offset": 3, "expected_success": True},
            ),
            # World 2: Weather capability needed
            InteractionEntry(
                user_input="What's the current weather in London?",
                check_type="gap_check",
                expected_hints=["weather", "London", "temperature"],
                metadata={"tick_offset": 5, "expected_missing": "weather"},
            ),
            InteractionEntry(
                user_input="Describe the London weather you found.",
                check_type="retry_check",
                expected_hints=["London", "weather", "temperature", "description"],
                metadata={"tick_offset": 7, "expected_success": True},
            ),
            # World 3: Calculator capability needed
            InteractionEntry(
                user_input="Calculate 2+2 and then multiply the result by 5.",
                check_type="gap_check",
                expected_hints=["calculate", "math", "result"],
                metadata={"tick_offset": 9, "expected_missing": "calc"},
            ),
            InteractionEntry(
                user_input="What was the result of the calculation?",
                check_type="retry_check",
                expected_hints=["20", "result", "calculated"],
                metadata={"tick_offset": 11, "expected_success": True},
            ),
            # World 4: Verification that already-acquired capabilities are reused
            InteractionEntry(
                user_input="Check the release page of lacebx/IdentityOS again for new releases.",
                check_type="reuse_check",
                expected_hints=["GitHub", "release", "check"],
                metadata={"tick_offset": 13, "previously_acquired": True},
            ),
            InteractionEntry(
                user_input="What's the temperature in Tokyo?",
                check_type="reuse_check",
                expected_hints=["weather", "Tokyo", "temperature"],
                metadata={"tick_offset": 15, "previously_acquired": True},
            ),
            # World 5: Try acquiring an already-installed capability (should detect duplicate)
            InteractionEntry(
                user_input="I need you to install the GitHub capability so you can check my repos.",
                check_type="duplicate_check",
                expected_hints=["already installed", "already have"],
                metadata={"tick_offset": 17, "already_installed": True},
            ),
            # World 6: New capability needed (filesystem)
            InteractionEntry(
                user_input="Read the contents of /etc/hostname and tell me what it says.",
                check_type="gap_check",
                expected_hints=["file", "read", "contents"],
                metadata={"tick_offset": 19, "expected_missing": "filesystem"},
            ),
            InteractionEntry(
                user_input="What was in the hostname file?",
                check_type="retry_check",
                expected_hints=["hostname", "file"],
                metadata={"tick_offset": 21, "expected_success": True},
            ),
        ]
        return self.entries
