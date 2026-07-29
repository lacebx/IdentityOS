from __future__ import annotations

from typing import Dict, List


class AdaptationMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        updated_beliefs = self._score_updated_beliefs()
        corrected_assumptions = self._score_corrected_assumptions()
        proactive_verification = self._score_proactive_verification()
        return {
            "updated_beliefs": updated_beliefs,
            "corrected_assumptions": corrected_assumptions,
            "proactive_verification": proactive_verification,
        }

    def _score_updated_beliefs(self) -> float:
        updates = [t for t in self.transcript if t.get("type") == "belief_update_check"]
        if not updates:
            return 50.0
        updated = 0
        for test in updates:
            response = (test.get("response") or "").lower()
            old_belief = (test.get("old_belief") or "").lower()
            new_belief = (test.get("new_belief") or "").lower()
            if new_belief and new_belief in response:
                updated += 1
            elif old_belief and old_belief not in response:
                updated += 0.5
        return round((updated / len(updates)) * 100, 1)

    def _score_corrected_assumptions(self) -> float:
        corrections = [t for t in self.transcript if t.get("type") == "correction_check"]
        if not corrections:
            return 50.0
        corrected = 0
        for test in corrections:
            response = (test.get("response") or "").lower()
            correct_keywords = ["you're right", "i stand corrected", "i was wrong", "my mistake",
                                "i apologize", "thank you for correcting", "you are correct",
                                "that's a good point"]
            if any(k in response for k in correct_keywords):
                corrected += 1
        return round((corrected / len(corrections)) * 100, 1)

    def _score_proactive_verification(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "proactive_check"]
        if not checks:
            return 50.0
        proactive = 0
        for test in checks:
            response = (test.get("response") or "").lower()
            proactive_keywords = ["let me check", "i'll verify", "i should look up", "let me search",
                                  "i will confirm", "let me find out", "let me research",
                                  "i'll get the latest", "let me fetch"]
            if any(k in response for k in proactive_keywords):
                proactive += 1
        return round((proactive / len(checks)) * 100, 1)
