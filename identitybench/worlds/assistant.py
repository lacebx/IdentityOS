from __future__ import annotations

from typing import List

from identitybench.worlds.base import BenchmarkWorld, InteractionEntry


class AssistantWorld(BenchmarkWorld):
    name = "Assistant"
    description = "Measures whether the identity tracks changing user preferences over time, updates stored beliefs, and notices gradual shifts."
    total_days = 28

    def build_schedule(self) -> List[InteractionEntry]:
        self.entries = [
            InteractionEntry(
                user_input="Hello! Let me tell you about my setup. I use VSCode as my editor, I prefer dark mode, and my favorite font is JetBrains Mono.",
                check_type="general",
                expected_hints=["VSCode", "dark mode", "JetBrains Mono"],
                metadata={"tick_offset": 0},
            ),
            InteractionEntry(
                user_input="What do you know about my editor preferences?",
                check_type="preference_check",
                expected_hints=["VSCode"],
                metadata={"tick_offset": 2, "expected_preference": "VSCode"},
            ),
            InteractionEntry(
                user_input="I switched to Neovim actually. The modal editing is so much faster.",
                check_type="belief_update_check",
                expected_hints=["Neovim"],
                metadata={"tick_offset": 5, "new_belief": "Neovim", "old_belief": "VSCode"},
            ),
            InteractionEntry(
                user_input="What editor do I use?",
                check_type="preference_check",
                expected_hints=["Neovim"],
                metadata={"tick_offset": 7, "expected_preference": "Neovim"},
            ),
            InteractionEntry(
                user_input="Actually, I think I prefer Helix now. The built-in LSP support is amazing.",
                check_type="belief_update_check",
                expected_hints=["Helix"],
                metadata={"tick_offset": 10, "new_belief": "Helix", "old_belief": "Neovim"},
            ),
            InteractionEntry(
                user_input="I noticed I keep changing editors. What pattern do you see?",
                check_type="pattern_check",
                expected_hints=["pattern", "change", "editor", "switch"],
                metadata={"tick_offset": 12},
            ),
            InteractionEntry(
                user_input="Quick question: what's my current editor and font preference?",
                check_type="preference_check",
                expected_hints=["Helix", "JetBrains Mono"],
                metadata={"tick_offset": 15, "expected_preference": "Helix"},
            ),
            InteractionEntry(
                user_input="I'm thinking about trying Emacs but I'm not sure yet. What would you recommend?",
                check_type="general",
                expected_hints=["Emacs"],
                metadata={"tick_offset": 18},
            ),
            InteractionEntry(
                user_input="Do I still use VSCode?",
                check_type="recall_check",
                ground_truth="Helix",
                expected_hints=["Helix", "switched", "Neovim", "changed"],
                metadata={"tick_offset": 21},
            ),
            InteractionEntry(
                user_input="What have you learned about my preferences since we started talking?",
                check_type="self_correction_check",
                expected_hints=["editor", "Helix", "dark mode", "JetBrains Mono"],
                metadata={"tick_offset": 25},
            ),
        ]
        return self.entries
